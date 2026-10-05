const MAX_BODY_BYTES = 16 * 1024;
const RESOURCE_PATTERN = /^\/orders\/([0-9]+)$/;
const USER_ID_PATTERN = /^[0-9]+$/;
const SHA256_PATTERN = /^[0-9a-f]{64}$/;

type OrderNotification = {
  application_id: number | string;
  resource: string;
  user_id: number | string;
  topic: string;
  sent: string;
  received?: string;
  attempts?: number;
};

type NormalizedNotification = {
  resource: string;
  userId: string;
  sentAt: string;
};

function jsonResponse(status: number, body: Record<string, unknown>): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function normalizeNotification(
  value: unknown,
  expectedApplicationId: string,
): NormalizedNotification | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }

  const payload = value as Partial<OrderNotification>;
  const applicationId = String(payload.application_id ?? "");
  const userId = String(payload.user_id ?? "");
  const resource = payload.resource;
  const sent = payload.sent;

  if (
    applicationId !== expectedApplicationId ||
    !USER_ID_PATTERN.test(userId) ||
    typeof resource !== "string" ||
    !RESOURCE_PATTERN.test(resource) ||
    payload.topic !== "orders_v2" ||
    typeof sent !== "string" ||
    !Number.isFinite(Date.parse(sent))
  ) {
    return null;
  }

  return {
    resource,
    userId,
    sentAt: new Date(sent).toISOString(),
  };
}

async function sha256Hex(value: string): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  return Array.from(
    new Uint8Array(digest),
    (byte) => byte.toString(16).padStart(2, "0"),
  ).join("");
}

async function matchesCapabilityPath(
  pathname: string,
  expectedSecret: string,
): Promise<boolean> {
  const suppliedSecret = pathname.split("/").filter(Boolean).at(-1) ?? "";
  const [suppliedDigest, expectedDigest] = await Promise.all([
    crypto.subtle.digest("SHA-256", new TextEncoder().encode(suppliedSecret)),
    crypto.subtle.digest("SHA-256", new TextEncoder().encode(expectedSecret)),
  ]);
  const supplied = new Uint8Array(suppliedDigest);
  const expected = new Uint8Array(expectedDigest);
  let difference = 0;
  for (let index = 0; index < supplied.length; index += 1) {
    difference |= supplied[index] ^ expected[index];
  }
  return difference === 0 && suppliedSecret.length > 0;
}

export async function handleRequest(request: Request): Promise<Response> {
  if (request.method !== "POST") {
    return jsonResponse(405, { error: "method_not_allowed" });
  }

  const webhookPathSecret = Deno.env.get("MERCADOLIVRE_WEBHOOK_PATH_SECRET");
  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const applicationId = Deno.env.get("MERCADOLIVRE_DEV_CLIENT_ID");
  if (!webhookPathSecret || !supabaseUrl || !serviceRoleKey || !applicationId) {
    console.error("Webhook configuration is incomplete.");
    return jsonResponse(503, { error: "service_unavailable" });
  }

  if (
    !await matchesCapabilityPath(
      new URL(request.url).pathname,
      webhookPathSecret,
    )
  ) {
    return jsonResponse(404, { error: "not_found" });
  }

  const contentLength = Number(request.headers.get("content-length") ?? 0);
  if (contentLength > MAX_BODY_BYTES) {
    return jsonResponse(413, { error: "payload_too_large" });
  }

  let rawBody: string;
  try {
    rawBody = await request.text();
  } catch {
    return jsonResponse(400, { error: "invalid_body" });
  }
  if (new TextEncoder().encode(rawBody).byteLength > MAX_BODY_BYTES) {
    return jsonResponse(413, { error: "payload_too_large" });
  }

  let payload: unknown;
  try {
    payload = JSON.parse(rawBody);
  } catch {
    return jsonResponse(400, { error: "invalid_json" });
  }

  const normalized = normalizeNotification(payload, applicationId);
  if (!normalized) {
    return jsonResponse(400, { error: "invalid_notification" });
  }

  const deduplicationKey = await sha256Hex([
    applicationId,
    normalized.userId,
    "orders_v2",
    normalized.resource,
    normalized.sentAt,
  ].join(":"));
  if (!SHA256_PATTERN.test(deduplicationKey)) {
    console.error("Could not create webhook idempotency key.");
    return jsonResponse(500, { error: "internal_error" });
  }

  let enqueueResponse: Response;
  try {
    enqueueResponse = await fetch(
      supabaseUrl + "/rest/v1/rpc/enqueue_mercadolivre_order_webhook",
      {
        method: "POST",
        headers: {
          "apikey": serviceRoleKey,
          "authorization": "Bearer " + serviceRoleKey,
          "content-type": "application/json",
        },
        body: JSON.stringify({
          target_user_id: normalized.userId,
          target_resource: normalized.resource,
          target_sent_at: normalized.sentAt,
          target_deduplication_key: deduplicationKey,
          target_payload: payload,
        }),
        signal: AbortSignal.timeout(350),
      },
    );
  } catch (error) {
    console.error("Could not enqueue Mercado Livre order notification.", error);
    return jsonResponse(503, { error: "queue_unavailable" });
  }

  if (!enqueueResponse.ok) {
    console.error(
      "Mercado Livre order notification enqueue failed.",
      enqueueResponse.status,
    );
    return jsonResponse(503, { error: "queue_unavailable" });
  }

  let accepted: unknown;
  try {
    accepted = await enqueueResponse.json();
  } catch {
    console.error("Webhook queue returned an invalid response.");
    return jsonResponse(503, { error: "queue_unavailable" });
  }

  if (accepted !== true) {
    return jsonResponse(404, { error: "seller_not_connected" });
  }

  return new Response(null, { status: 200 });
}

export { matchesCapabilityPath, normalizeNotification, sha256Hex };

if (import.meta.main) {
  Deno.serve(handleRequest);
}

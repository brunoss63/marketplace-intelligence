import { decryptFernet, encryptFernet } from "../_shared/fernet.ts";

const MAX_ATTEMPTS = 12;
const MISSED_FEEDS_PAGE_SIZE = 50;
const MISSED_FEEDS_MAX_PAGES = 20;
const ORDER_RESOURCE_PATTERN = /^\/orders\/([0-9]+)$/;
const RETRYABLE_HTTP_STATUSES = new Set([
  404,
  408,
  425,
  429,
  500,
  502,
  503,
  504,
]);

class PermanentProcessingError extends Error {}

class RetryableProcessingError extends Error {}

class ReconciliationError extends Error {
  constructor(
    readonly phase: string,
    options?: ErrorOptions,
    readonly diagnostic?: string,
  ) {
    super(`Missed-feeds reconciliation failed during ${phase}.`, options);
  }
}

type WebhookEvent = {
  id: string;
  tenant_id: string;
  external_user_id: string;
  resource: string;
  event_sent_at: string;
  attempt_count: number;
  lease_id: string;
};

type MarketplaceConnection = {
  tenant_id: string;
  external_user_id: string;
  access_token_encrypted: string;
  refresh_token_encrypted: string;
  expires_at: string;
  refresh_lease_id: string | null;
  refresh_lease_until: string | null;
};

type MarketplaceOrder = {
  id: number | string;
  date_created: string;
  status: string;
  currency_id?: string;
  order_items: Array<{
    item: {
      id: string;
      title?: string;
      seller_custom_field?: string;
      seller_sku?: string;
      attributes?: Array<{ id?: string; value_name?: string }>;
    };
    quantity: number;
    unit_price: number;
    full_unit_price?: number;
    currency_id?: string;
    variation_id?: number | string;
  }>;
};

type CanonicalOrder = {
  order_id: string;
  order_date: string;
  marketplace: "Mercado Livre";
  sku: string;
  product_name: string;
  quantity: number;
  unit_price: number;
  gross_revenue: number;
  discount: number;
  status: string;
};

type MissedFeedPage = {
  messages?: unknown[];
  results?: unknown[];
};

function jsonResponse(status: number, body: Record<string, unknown>): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

export function retryDelaySeconds(attempt: number): number {
  return Math.min(60 * 60, 5 * 2 ** Math.min(attempt - 1, 10));
}

function canonicalStatus(value: string): string {
  switch (value.trim().toLowerCase()) {
    case "paid":
    case "settled":
    case "fulfilled":
    case "finished":
    case "delivered":
      return "Concluído";
    case "cancelled":
    case "canceled":
    case "invalid":
      return "Cancelado";
    case "returned":
    case "refunded":
      return "Devolvido";
    case "confirmed":
    case "payment_required":
    case "payment_in_process":
    case "partially_paid":
    case "in_process":
    case "shipped":
      return "Em andamento";
    default:
      throw new PermanentProcessingError(
        "Unsupported Mercado Livre order status.",
      );
  }
}

function publicationSku(
  item: MarketplaceOrder["order_items"][number]["item"],
  variationId: number | string | undefined,
): string {
  if (typeof item.seller_sku === "string" && item.seller_sku.trim()) {
    return item.seller_sku.trim();
  }
  if (
    typeof item.seller_custom_field === "string" &&
    item.seller_custom_field.trim()
  ) {
    return item.seller_custom_field.trim();
  }
  const sellerSkuAttribute = item.attributes?.find((attribute) =>
    attribute.id === "SELLER_SKU"
  )?.value_name;
  if (sellerSkuAttribute?.trim()) {
    return sellerSkuAttribute.trim();
  }
  return variationId === undefined ? item.id : `${item.id}-${variationId}`;
}

export function normalizeOrder(order: MarketplaceOrder): CanonicalOrder[] {
  if (
    order.id === undefined ||
    !Number.isFinite(Date.parse(order.date_created)) ||
    !Array.isArray(order.order_items) ||
    order.order_items.length === 0
  ) {
    throw new Error("Invalid Mercado Livre order payload.");
  }
  const status = canonicalStatus(order.status);
  const orderDate = order.date_created.slice(0, 10);
  const aggregated = new Map<string, CanonicalOrder>();

  for (const line of order.order_items) {
    if (
      !line.item ||
      typeof line.item.id !== "string" ||
      !line.item.id.trim() ||
      !Number.isFinite(line.quantity) ||
      line.quantity <= 0 ||
      !Number.isFinite(line.unit_price) ||
      line.unit_price < 0 ||
      (line.full_unit_price !== undefined &&
        (!Number.isFinite(line.full_unit_price) ||
          line.full_unit_price < line.unit_price)) ||
      ((line.currency_id ?? order.currency_id) !== undefined &&
        (line.currency_id ?? order.currency_id) !== "BRL")
    ) {
      throw new PermanentProcessingError("Invalid Mercado Livre order item.");
    }

    const sku = publicationSku(line.item, line.variation_id);
    const productName = line.item.title?.trim() || line.item.id;
    const key = JSON.stringify([String(order.id), sku, productName]);
    const current: CanonicalOrder = aggregated.get(key) ?? {
      order_id: String(order.id),
      order_date: orderDate,
      marketplace: "Mercado Livre",
      sku,
      product_name: productName,
      quantity: 0,
      unit_price: 0,
      gross_revenue: 0,
      discount: 0,
      status,
    };
    const fullUnitPrice = line.full_unit_price ?? line.unit_price;
    current.quantity += line.quantity;
    current.gross_revenue += fullUnitPrice * line.quantity;
    current.discount += (fullUnitPrice - line.unit_price) * line.quantity;
    current.unit_price = current.gross_revenue / current.quantity;
    aggregated.set(key, current);
  }

  return Array.from(aggregated.values());
}

async function serviceRequest(
  baseUrl: string,
  serviceRoleKey: string,
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  return await fetch(`${baseUrl}/rest/v1/${path}`, {
    ...init,
    headers: {
      "apikey": serviceRoleKey,
      "authorization": `Bearer ${serviceRoleKey}`,
      ...init.headers,
    },
    signal: init.signal ?? AbortSignal.timeout(12_000),
  });
}

async function readConnection(
  event: WebhookEvent,
  baseUrl: string,
  serviceRoleKey: string,
): Promise<MarketplaceConnection> {
  const query = new URLSearchParams({
    select:
      "tenant_id,external_user_id,access_token_encrypted,refresh_token_encrypted,expires_at,refresh_lease_id,refresh_lease_until",
    tenant_id: `eq.${event.tenant_id}`,
    marketplace: "eq.Mercado Livre",
    external_user_id: `eq.${event.external_user_id}`,
    limit: "1",
  });
  const response = await serviceRequest(
    baseUrl,
    serviceRoleKey,
    `marketplace_connections?${query.toString()}`,
  );
  if (!response.ok) {
    throw new Error(
      `Could not read marketplace connection (${response.status}).`,
    );
  }
  const connections = await response.json() as MarketplaceConnection[];
  if (
    connections.length !== 1 ||
    connections[0].external_user_id !== event.external_user_id
  ) {
    throw new Error("Marketplace connection is missing or mismatched.");
  }
  return connections[0];
}

async function updateConnection(
  connection: MarketplaceConnection,
  leaseId: string,
  tokens: Record<string, unknown>,
  key: string,
  baseUrl: string,
  serviceRoleKey: string,
): Promise<void> {
  const response = await serviceRequest(
    baseUrl,
    serviceRoleKey,
    "marketplace_connections?tenant_id=eq." +
      encodeURIComponent(connection.tenant_id) +
      "&marketplace=eq.Mercado%20Livre&refresh_lease_id=eq." +
      encodeURIComponent(leaseId),
    {
      method: "PATCH",
      headers: {
        "content-type": "application/json",
        "prefer": "return=representation",
      },
      body: JSON.stringify({
        access_token_encrypted: await encryptFernet(
          String(tokens.access_token),
          key,
        ),
        refresh_token_encrypted: await encryptFernet(
          String(tokens.refresh_token),
          key,
        ),
        scope: String(tokens.scope ?? ""),
        expires_at: new Date(
          Date.now() + Number(tokens.expires_in) * 1000,
        ).toISOString(),
        refresh_lease_id: null,
        refresh_lease_until: null,
        updated_at: new Date().toISOString(),
      }),
    },
  );
  if (!response.ok) {
    throw new Error(`Could not persist refreshed tokens (${response.status}).`);
  }
  const updated = await response.json() as MarketplaceConnection[];
  if (updated.length !== 1) {
    throw new Error("Refresh lease was lost before token persistence.");
  }
}

async function refreshAccessToken(
  connection: MarketplaceConnection,
  key: string,
  clientId: string,
  clientSecret: string,
  baseUrl: string,
  serviceRoleKey: string,
): Promise<string> {
  const leaseId = crypto.randomUUID();
  const claim = await serviceRequest(
    baseUrl,
    serviceRoleKey,
    "rpc/claim_marketplace_token_refresh",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        target_tenant_id: connection.tenant_id,
        target_lease_id: leaseId,
      }),
    },
  );
  if (!claim.ok) {
    throw new Error(`Could not claim token refresh lease (${claim.status}).`);
  }
  const claimed = await claim.json();
  if (claimed !== true) {
    throw new Error("Token refresh is already in progress.");
  }

  try {
    const refreshToken = await decryptFernet(
      connection.refresh_token_encrypted,
      key,
    );
    const body = new URLSearchParams({
      grant_type: "refresh_token",
      client_id: clientId,
      client_secret: clientSecret,
      refresh_token: refreshToken,
    });
    const response = await fetch("https://api.mercadolibre.com/oauth/token", {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body,
      signal: AbortSignal.timeout(10_000),
    });
    if (!response.ok) {
      throw new Error(
        `Mercado Livre token refresh failed (${response.status}).`,
      );
    }
    const tokens = await response.json() as Record<string, unknown>;
    if (
      !tokens.access_token ||
      !tokens.refresh_token ||
      typeof tokens.expires_in !== "number" ||
      !Number.isInteger(tokens.expires_in) ||
      String(tokens.user_id) !== connection.external_user_id
    ) {
      throw new Error("Mercado Livre returned an invalid rotated token.");
    }
    await updateConnection(
      connection,
      leaseId,
      tokens,
      key,
      baseUrl,
      serviceRoleKey,
    );
    return String(tokens.access_token);
  } finally {
    const release = await serviceRequest(
      baseUrl,
      serviceRoleKey,
      "rpc/release_marketplace_token_refresh",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          target_tenant_id: connection.tenant_id,
          target_lease_id: leaseId,
        }),
      },
    );
    if (!release.ok) {
      console.error("Could not release token refresh lease.", release.status);
    }
  }
}

async function accessTokenFor(
  connection: MarketplaceConnection,
  key: string,
  clientId: string,
  clientSecret: string,
  baseUrl: string,
  serviceRoleKey: string,
): Promise<string> {
  if (Date.parse(connection.expires_at) <= Date.now() + 120_000) {
    return await refreshAccessToken(
      connection,
      key,
      clientId,
      clientSecret,
      baseUrl,
      serviceRoleKey,
    );
  }
  return await decryptFernet(connection.access_token_encrypted, key);
}

function missedFeedMessages(value: unknown): unknown[] {
  if (Array.isArray(value)) {
    return value;
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("Mercado Livre returned an invalid missed_feeds response.");
  }
  const page = value as MissedFeedPage;
  const messages = page.messages ?? page.results;
  if (
    messages === undefined &&
    (page.messages === null || page.results === null)
  ) {
    return [];
  }
  if (!Array.isArray(messages)) {
    throw new Error(
      "Mercado Livre missed_feeds response has no messages array.",
    );
  }
  return messages;
}

function missedFeedEnvelopeShape(value: unknown): string {
  if (value === null) {
    return "null";
  }
  if (Array.isArray(value)) {
    return "array";
  }
  if (typeof value !== "object") {
    return typeof value;
  }
  const describe = (record: Record<string, unknown>, depth: number): string => {
    const fields = Object.entries(record)
      .filter(([key]) => /^[a-zA-Z_]{1,30}$/.test(key))
      .slice(0, 8)
      .map(([key, field]) => {
        if (Array.isArray(field)) {
          return `${key}_array`;
        }
        if (field === null) {
          return `${key}_null`;
        }
        if (typeof field === "object" && depth < 2) {
          return `${key}_object_${
            describe(field as Record<string, unknown>, depth + 1)
          }`;
        }
        return `${key}_${typeof field}`;
      });
    return fields.join("_") || "no_keys";
  };
  return `object_${describe(value as Record<string, unknown>, 0)}`;
}

function normalizeMissedFeedNotification(
  value: unknown,
  expectedApplicationId: string,
): {
  resource: string;
  userId: string;
  sentAt: string;
  payload: Record<string, unknown>;
} | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  const notification = value as Record<string, unknown>;
  if (notification.topic !== "orders_v2") {
    return null;
  }
  if (
    notification.application_id !== undefined &&
    String(notification.application_id) !== expectedApplicationId
  ) {
    throw new Error("Missed feed contains a mismatched application ID.");
  }
  const userId = String(notification.user_id ?? "");
  const resource = notification.resource;
  const sent = notification.sent;
  if (
    !/^[0-9]+$/.test(userId) ||
    typeof resource !== "string" ||
    !ORDER_RESOURCE_PATTERN.test(resource) ||
    typeof sent !== "string" ||
    !Number.isFinite(Date.parse(sent))
  ) {
    throw new Error("Missed feed contains an invalid orders_v2 notification.");
  }
  const normalized = {
    resource,
    userId,
    sentAt: new Date(sent).toISOString(),
  };
  return {
    ...normalized,
    payload: {
      application_id: expectedApplicationId,
      resource: normalized.resource,
      user_id: normalized.userId,
      topic: "orders_v2",
      sent: normalized.sentAt,
      ...(typeof notification.received === "string"
        ? { received: notification.received }
        : {}),
      ...(typeof notification.attempts === "number" ||
          typeof notification.attempts === "string"
        ? { attempts: notification.attempts }
        : {}),
    },
  };
}

async function enqueueMissedFeedNotification(
  notification: {
    resource: string;
    userId: string;
    sentAt: string;
    payload: Record<string, unknown>;
  },
  applicationId: string,
  baseUrl: string,
  serviceRoleKey: string,
): Promise<boolean> {
  const deduplicationKey = await sha256Hex([
    applicationId,
    notification.userId,
    "orders_v2",
    notification.resource,
    notification.sentAt,
  ].join(":"));
  const response = await serviceRequest(
    baseUrl,
    serviceRoleKey,
    "rpc/enqueue_mercadolivre_order_webhook",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        target_user_id: notification.userId,
        target_resource: notification.resource,
        target_sent_at: notification.sentAt,
        target_deduplication_key: deduplicationKey,
        target_payload: notification.payload,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(
      `Could not enqueue missed Mercado Livre event (${response.status}).`,
    );
  }
  const accepted: unknown = await response.json();
  if (typeof accepted !== "boolean") {
    throw new Error("Webhook queue returned an invalid response.");
  }
  if (!accepted) {
    throw new Error("Missed feed seller is no longer connected.");
  }
  return accepted;
}

async function readMarketplaceConnections(
  baseUrl: string,
  serviceRoleKey: string,
): Promise<MarketplaceConnection[]> {
  const query = new URLSearchParams({
    select:
      "tenant_id,external_user_id,access_token_encrypted,refresh_token_encrypted,expires_at,refresh_lease_id,refresh_lease_until",
    marketplace: "eq.Mercado Livre",
  });
  const response = await serviceRequest(
    baseUrl,
    serviceRoleKey,
    `marketplace_connections?${query.toString()}`,
  );
  if (!response.ok) {
    throw new Error(
      `Could not list Mercado Livre connections (${response.status}).`,
    );
  }
  const connections: unknown = await response.json();
  if (
    !Array.isArray(connections) ||
    connections.some((connection) =>
      typeof connection !== "object" || connection === null
    )
  ) {
    throw new Error("Marketplace connection query returned invalid data.");
  }
  return connections as MarketplaceConnection[];
}

async function fetchMissedFeedsPage(
  accessToken: string,
  applicationId: string,
  offset: number,
): Promise<unknown[]> {
  const query = new URLSearchParams({
    app_id: applicationId,
    topic: "orders_v2",
    limit: String(MISSED_FEEDS_PAGE_SIZE),
    offset: String(offset),
  });
  let response: Response;
  try {
    response = await fetch(
      `https://api.mercadolibre.com/missed_feeds?${query.toString()}`,
      {
        headers: { "authorization": `Bearer ${accessToken}` },
        signal: AbortSignal.timeout(12_000),
      },
    );
  } catch (error) {
    throw new ReconciliationError("missed_feeds_network", { cause: error });
  }
  if (!response.ok) {
    throw new ReconciliationError(`missed_feeds_http_${response.status}`);
  }
  let page: unknown;
  try {
    page = await response.json();
  } catch (error) {
    throw new ReconciliationError("missed_feeds_invalid_json", {
      cause: error,
    });
  }
  try {
    return missedFeedMessages(page);
  } catch (error) {
    throw new ReconciliationError("missed_feeds_invalid_envelope", {
      cause: error,
    }, missedFeedEnvelopeShape(page));
  }
}

async function reconcileMissedFeeds(config: {
  baseUrl: string;
  serviceRoleKey: string;
  encryptionKey: string;
  clientId: string;
  clientSecret: string;
}): Promise<{ sellers: number; pages: number; accepted: number }> {
  let connections: MarketplaceConnection[];
  try {
    connections = await readMarketplaceConnections(
      config.baseUrl,
      config.serviceRoleKey,
    );
  } catch (error) {
    throw new ReconciliationError("connections", { cause: error });
  }
  const connectionBySeller = new Map<string, MarketplaceConnection>();
  for (const connection of connections) {
    if (!/^[0-9]+$/.test(connection.external_user_id)) {
      throw new Error("Marketplace connection has an invalid seller ID.");
    }
    connectionBySeller.set(
      connection.external_user_id,
      connectionBySeller.get(connection.external_user_id) ?? connection,
    );
  }

  let pages = 0;
  let accepted = 0;
  for (const [sellerId, connection] of connectionBySeller) {
    let accessToken: string;
    try {
      accessToken = await accessTokenFor(
        connection,
        config.encryptionKey,
        config.clientId,
        config.clientSecret,
        config.baseUrl,
        config.serviceRoleKey,
      );
    } catch (error) {
      throw new ReconciliationError("seller_token", { cause: error });
    }
    let offset = 0;
    let sellerPages = 0;
    while (true) {
      let messages: unknown[];
      try {
        messages = await fetchMissedFeedsPage(
          accessToken,
          config.clientId,
          offset,
        );
      } catch (error) {
        if (error instanceof ReconciliationError) {
          throw error;
        }
        throw new ReconciliationError("missed_feeds_api", { cause: error });
      }
      pages += 1;
      sellerPages += 1;
      if (messages.length === 0) {
        break;
      }
      for (const message of messages) {
        let notification: ReturnType<typeof normalizeMissedFeedNotification>;
        try {
          notification = normalizeMissedFeedNotification(
            message,
            config.clientId,
          );
        } catch (error) {
          throw new ReconciliationError("missed_feed_validation", {
            cause: error,
          });
        }
        if (!notification || notification.userId !== sellerId) {
          continue;
        }
        try {
          if (
            await enqueueMissedFeedNotification(
              notification,
              config.clientId,
              config.baseUrl,
              config.serviceRoleKey,
            )
          ) {
            accepted += 1;
          }
        } catch (error) {
          throw new ReconciliationError("inbox_enqueue", { cause: error });
        }
      }
      offset += messages.length;
      if (sellerPages >= MISSED_FEEDS_MAX_PAGES) {
        throw new Error(
          `Missed Mercado Livre feed exceeded ${MISSED_FEEDS_MAX_PAGES} pages for seller ${sellerId}.`,
        );
      }
    }
  }
  return { sellers: connectionBySeller.size, pages, accepted };
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

async function loadOrder(
  resource: string,
  accessToken: string,
): Promise<MarketplaceOrder> {
  const match = ORDER_RESOURCE_PATTERN.exec(resource);
  if (!match) {
    throw new Error("Invalid queued order resource.");
  }
  const response = await fetch(
    `https://api.mercadolibre.com/orders/${match[1]}`,
    {
      headers: { "authorization": `Bearer ${accessToken}` },
      signal: AbortSignal.timeout(12_000),
    },
  );
  if (!response.ok) {
    const error = new Error(`Order API request failed (${response.status}).`);
    if (RETRYABLE_HTTP_STATUSES.has(response.status)) {
      throw new RetryableProcessingError(error.message);
    }
    throw new PermanentProcessingError(error.message);
  }
  return await response.json() as MarketplaceOrder;
}

async function persistOrder(
  event: WebhookEvent,
  order: MarketplaceOrder,
  baseUrl: string,
  serviceRoleKey: string,
): Promise<void> {
  if (String(order.id) !== event.resource.slice("/orders/".length)) {
    throw new PermanentProcessingError(
      "Order API returned a different order than requested.",
    );
  }
  const rows = normalizeOrder(order);
  if (rows.length === 0) {
    return;
  }

  const existingQuery = new URLSearchParams({
    select: "sku,product_name,marketplace_fee,seller_shipping",
    tenant_id: `eq.${event.tenant_id}`,
    marketplace: "eq.Mercado Livre",
    order_id: `eq.${String(order.id)}`,
  });
  const existingResponse = await serviceRequest(
    baseUrl,
    serviceRoleKey,
    `orders?${existingQuery.toString()}`,
  );
  if (!existingResponse.ok) {
    throw new Error(
      `Could not read existing order rows (${existingResponse.status}).`,
    );
  }
  const existingRows = await existingResponse.json() as Array<{
    sku: string;
    product_name: string;
    marketplace_fee: number;
    seller_shipping: number;
  }>;
  const existing = new Map(
    existingRows.map((row) => [
      JSON.stringify([row.sku, row.product_name]),
      row,
    ]),
  );
  const payload = rows.map((row) => {
    const prior = existing.get(JSON.stringify([row.sku, row.product_name]));
    return {
      tenant_id: event.tenant_id,
      marketplace: row.marketplace,
      order_id: row.order_id,
      order_date: row.order_date,
      sku: row.sku,
      product_name: row.product_name,
      quantity: row.quantity,
      unit_price: row.unit_price,
      gross_revenue: row.gross_revenue,
      discount: row.discount,
      marketplace_fee: prior?.marketplace_fee ?? 0,
      seller_shipping: prior?.seller_shipping ?? 0,
      status: row.status,
      updated_at: new Date().toISOString(),
    };
  });
  const query = new URLSearchParams({
    on_conflict: "tenant_id,marketplace,order_id,sku,product_name",
  });
  const response = await serviceRequest(
    baseUrl,
    serviceRoleKey,
    `orders?${query.toString()}`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "prefer": "resolution=merge-duplicates,return=minimal",
      },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    throw new Error(
      `Could not persist Mercado Livre order (${response.status}).`,
    );
  }
}

async function updateEvent(
  event: WebhookEvent,
  baseUrl: string,
  serviceRoleKey: string,
  values: Record<string, unknown>,
): Promise<void> {
  const query = new URLSearchParams({
    id: `eq.${event.id}`,
    lease_id: `eq.${event.lease_id}`,
    select: "id",
  });
  const response = await serviceRequest(
    baseUrl,
    serviceRoleKey,
    `marketplace_webhook_events?${query.toString()}`,
    {
      method: "PATCH",
      headers: {
        "content-type": "application/json",
        "prefer": "return=representation",
      },
      body: JSON.stringify({ ...values, updated_at: new Date().toISOString() }),
    },
  );
  if (!response.ok) {
    throw new Error(`Could not update webhook event (${response.status}).`);
  }
  const updated = await response.json() as Array<{ id: string }>;
  if (updated.length !== 1) {
    throw new Error("Webhook event processing lease was lost.");
  }
}

function isRetryable(error: unknown): boolean {
  return !(error instanceof PermanentProcessingError);
}

async function processEvent(
  event: WebhookEvent,
  config: {
    baseUrl: string;
    serviceRoleKey: string;
    encryptionKey: string;
    clientId: string;
    clientSecret: string;
  },
): Promise<void> {
  try {
    if (event.attempt_count > MAX_ATTEMPTS) {
      await updateEvent(event, config.baseUrl, config.serviceRoleKey, {
        status: "failed",
        lease_id: null,
        lease_until: null,
        last_error: "Maximum processing attempts exceeded.",
      });
      return;
    }
    const connection = await readConnection(
      event,
      config.baseUrl,
      config.serviceRoleKey,
    );
    const token = await accessTokenFor(
      connection,
      config.encryptionKey,
      config.clientId,
      config.clientSecret,
      config.baseUrl,
      config.serviceRoleKey,
    );
    const order = await loadOrder(event.resource, token);
    if (String(order.id) !== event.resource.slice("/orders/".length)) {
      throw new Error("Order API returned a different order than requested.");
    }
    await persistOrder(
      event,
      order,
      config.baseUrl,
      config.serviceRoleKey,
    );
    await updateEvent(event, config.baseUrl, config.serviceRoleKey, {
      status: "processed",
      lease_id: null,
      lease_until: null,
      last_error: null,
      processed_at: new Date().toISOString(),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error.";
    const terminal = event.attempt_count >= MAX_ATTEMPTS || !isRetryable(error);
    await updateEvent(event, config.baseUrl, config.serviceRoleKey, {
      status: terminal ? "failed" : "pending",
      lease_id: null,
      lease_until: null,
      next_attempt_at: new Date(
        Date.now() + retryDelaySeconds(event.attempt_count) * 1000,
      ).toISOString(),
      last_error: message.slice(0, 500),
    });
    console.error("Mercado Livre order webhook processing failed.", message);
  }
}

export async function handleRequest(request: Request): Promise<Response> {
  if (request.method !== "POST") {
    return jsonResponse(405, { error: "method_not_allowed" });
  }
  if (
    !await matchesBearerSecret(
      request.headers.get("authorization") ?? "",
      Deno.env.get("MERCADOLIVRE_WORKER_SECRET") ?? "",
    )
  ) {
    return jsonResponse(401, { error: "unauthorized" });
  }

  const workerSecret = Deno.env.get("MERCADOLIVRE_WORKER_SECRET");
  const baseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const encryptionKey = Deno.env.get("MERCADOLIVRE_DEV_TOKEN_ENCRYPTION_KEY");
  const clientId = Deno.env.get("MERCADOLIVRE_DEV_CLIENT_ID");
  const clientSecret = Deno.env.get("MERCADOLIVRE_DEV_CLIENT_SECRET");
  if (
    !workerSecret || !baseUrl || !serviceRoleKey || !encryptionKey ||
    !clientId || !clientSecret
  ) {
    console.error("Mercado Livre worker configuration is incomplete.");
    return jsonResponse(503, { error: "service_unavailable" });
  }
  const config = {
    baseUrl,
    serviceRoleKey,
    encryptionKey,
    clientId,
    clientSecret,
  };
  let reconciliation: {
    sellers: number;
    pages: number;
    accepted: number;
  } | undefined;
  if (new URL(request.url).searchParams.get("mode") === "reconcile") {
    try {
      reconciliation = await reconcileMissedFeeds(config);
    } catch (error) {
      console.error("Could not reconcile missed Mercado Livre feeds.", error);
      return jsonResponse(503, {
        error: "reconciliation_unavailable",
        phase: error instanceof ReconciliationError ? error.phase : "unknown",
        ...(error instanceof ReconciliationError && error.diagnostic
          ? { diagnostic: error.diagnostic }
          : {}),
      });
    }
  }
  const leaseId = crypto.randomUUID();
  let claimResponse: Response;
  try {
    claimResponse = await serviceRequest(
      baseUrl,
      serviceRoleKey,
      "rpc/claim_mercadolivre_order_webhooks",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          target_lease_id: leaseId,
          target_batch_size: 1,
        }),
      },
    );
  } catch (error) {
    console.error("Could not claim order webhook events.", error);
    return jsonResponse(503, { error: "queue_unavailable" });
  }
  if (!claimResponse.ok) {
    console.error(
      "Could not claim order webhook events.",
      claimResponse.status,
    );
    return jsonResponse(503, { error: "queue_unavailable" });
  }

  const events = await claimResponse.json() as WebhookEvent[];
  for (const event of events) {
    await processEvent(event, config);
  }
  return jsonResponse(200, {
    processed: events.length,
    ...(reconciliation ? { reconciliation } : {}),
  });
}

async function matchesBearerSecret(
  authorization: string,
  expectedSecret: string,
): Promise<boolean> {
  const prefix = "Bearer ";
  if (!authorization.startsWith(prefix) || expectedSecret.length === 0) {
    return false;
  }
  const supplied = authorization.slice(prefix.length);
  const [suppliedDigest, expectedDigest] = await Promise.all([
    crypto.subtle.digest("SHA-256", new TextEncoder().encode(supplied)),
    crypto.subtle.digest("SHA-256", new TextEncoder().encode(expectedSecret)),
  ]);
  const left = new Uint8Array(suppliedDigest);
  const right = new Uint8Array(expectedDigest);
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left[index] ^ right[index];
  }
  return difference === 0 && supplied.length > 0;
}

export { matchesBearerSecret };
export {
  missedFeedMessages,
  normalizeMissedFeedNotification,
  reconcileMissedFeeds,
};

if (import.meta.main) {
  Deno.serve(handleRequest);
}

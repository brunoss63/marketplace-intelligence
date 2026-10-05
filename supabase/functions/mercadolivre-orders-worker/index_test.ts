import { decryptFernet, encryptFernet } from "../_shared/fernet.ts";
import {
  matchesBearerSecret,
  missedFeedMessages,
  normalizeMissedFeedNotification,
  normalizeOrder,
  reconcileMissedFeeds,
  retryDelaySeconds,
} from "./index.ts";

function assert(condition: boolean): void {
  if (!condition) {
    throw new Error("Assertion failed");
  }
}

function assertEquals(actual: unknown, expected: unknown): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(
      `Expected ${JSON.stringify(expected)}, received ${
        JSON.stringify(actual)
      }`,
    );
  }
}

Deno.test("decrypts and re-encrypts Fernet tokens", async () => {
  const key = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  const encrypted = await encryptFernet("access-token", key);
  assertEquals(await decryptFernet(encrypted, key), "access-token");
});

Deno.test("normalizes and aggregates repeated lines in an order", () => {
  const rows = normalizeOrder({
    id: 123,
    date_created: "2026-10-05T00:30:00-03:00",
    status: "paid",
    currency_id: "BRL",
    order_items: [
      {
        item: { id: "MLB1", title: "Product", seller_custom_field: "SKU-1" },
        quantity: 1,
        unit_price: 80,
        full_unit_price: 100,
      },
      {
        item: { id: "MLB1", title: "Product", seller_custom_field: "SKU-1" },
        quantity: 2,
        unit_price: 90,
        full_unit_price: 100,
      },
    ],
  });

  assertEquals(rows.length, 1);
  assertEquals(rows[0].order_date, "2026-10-05");
  assertEquals(rows[0].quantity, 3);
  assertEquals(rows[0].gross_revenue, 300);
  assertEquals(rows[0].discount, 40);
  assertEquals(rows[0].status, "Concluído");
});

Deno.test("applies bounded retry delays", () => {
  assertEquals(retryDelaySeconds(1), 5);
  assertEquals(retryDelaySeconds(4), 40);
  assertEquals(retryDelaySeconds(12), 3600);
});

Deno.test("normalizes missed orders feeds for the configured application", () => {
  const event = normalizeMissedFeedNotification(
    {
      resource: "/orders/123",
      user_id: 456,
      topic: "orders_v2",
      sent: "2026-10-05T18:00:00.000Z",
      attempts: 3,
    },
    "789",
  );
  assertEquals(event, {
    resource: "/orders/123",
    userId: "456",
    sentAt: "2026-10-05T18:00:00.000Z",
    payload: {
      application_id: "789",
      resource: "/orders/123",
      user_id: "456",
      topic: "orders_v2",
      sent: "2026-10-05T18:00:00.000Z",
      attempts: 3,
    },
  });
  assertEquals(
    normalizeMissedFeedNotification(
      {
        resource: "/orders/123",
        user_id: 456,
        topic: "items",
        sent: "2026-10-05T18:00:00.000Z",
      },
      "789",
    ),
    null,
  );
  let rejectedApplication = false;
  try {
    normalizeMissedFeedNotification(
      {
        application_id: "other-app",
        resource: "/orders/123",
        user_id: 456,
        topic: "orders_v2",
        sent: "2026-10-05T18:00:00.000Z",
      },
      "789",
    );
  } catch {
    rejectedApplication = true;
  }
  assert(rejectedApplication);
});

Deno.test("accepts both documented missed feed page envelopes", () => {
  assertEquals(missedFeedMessages({ messages: [1] }), [1]);
  assertEquals(missedFeedMessages({ results: [2] }), [2]);
  assertEquals(missedFeedMessages([3]), [3]);
  assertEquals(missedFeedMessages({ messages: null }), []);
});

Deno.test("reconciles and enqueues missed order events with pagination", async () => {
  const key = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  const encryptedToken = await encryptFernet("access-token", key);
  const originalFetch = globalThis.fetch;
  const requests: Array<{ url: string; body: string | undefined }> = [];
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    requests.push({
      url,
      body: typeof init?.body === "string" ? init.body : undefined,
    });
    if (
      url.startsWith("https://project.test/rest/v1/marketplace_connections?")
    ) {
      return Response.json([{
        tenant_id: "tenant-1",
        external_user_id: "456",
        access_token_encrypted: encryptedToken,
        refresh_token_encrypted: encryptedToken,
        expires_at: "2099-01-01T00:00:00.000Z",
        refresh_lease_id: null,
        refresh_lease_until: null,
      }]);
    }
    if (url.startsWith("https://api.mercadolibre.com/missed_feeds?")) {
      const offset = new URL(url).searchParams.get("offset");
      return Response.json(
        offset === "0"
          ? {
            messages: [{
              application_id: "789",
              resource: "/orders/123",
              user_id: "456",
              topic: "orders_v2",
              sent: "2026-10-05T18:00:00.000Z",
            }],
          }
          : { messages: [] },
      );
    }
    if (url.includes("/rpc/enqueue_mercadolivre_order_webhook")) {
      return Response.json(true);
    }
    throw new Error(`Unexpected reconciliation request: ${url}`);
  };

  try {
    const result = await reconcileMissedFeeds({
      baseUrl: "https://project.test",
      serviceRoleKey: "service-role-test",
      encryptionKey: key,
      clientId: "789",
      clientSecret: "client-secret-test",
    });
    assertEquals(result, { sellers: 1, pages: 2, accepted: 1 });
    const enqueue = requests.find((request) =>
      request.url.includes("/rpc/enqueue_mercadolivre_order_webhook")
    );
    if (!enqueue?.body) {
      throw new Error("Expected the reconciliation to enqueue one event.");
    }
    const payload = JSON.parse(enqueue.body);
    assertEquals(payload.target_user_id, "456");
    assertEquals(payload.target_resource, "/orders/123");
    assert(/^[0-9a-f]{64}$/.test(payload.target_deduplication_key));
  } finally {
    globalThis.fetch = originalFetch;
  }
});

Deno.test("rejects unauthenticated worker requests", async () => {
  assertEquals(
    await matchesBearerSecret("Bearer wrong", "expected-secret"),
    false,
  );
  assertEquals(
    await matchesBearerSecret("Bearer expected-secret", "expected-secret"),
    true,
  );
});

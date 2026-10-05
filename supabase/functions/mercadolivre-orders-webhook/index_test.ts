import {
  handleRequest,
  matchesCapabilityPath,
  normalizeNotification,
  sha256Hex,
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

Deno.test("accepts an orders_v2 event for the configured application", () => {
  const result = normalizeNotification(
    {
      application_id: 12345,
      resource: "/orders/987654321",
      user_id: 67890,
      topic: "orders_v2",
      sent: "2026-10-05T18:00:00.000Z",
    },
    "12345",
  );

  assertEquals(result, {
    resource: "/orders/987654321",
    userId: "67890",
    sentAt: "2026-10-05T18:00:00.000Z",
  });
});

Deno.test("rejects a mismatched application, topic, and resource", () => {
  const base = {
    application_id: 12345,
    resource: "/orders/987654321",
    user_id: 67890,
    topic: "orders_v2",
    sent: "2026-10-05T18:00:00.000Z",
  };

  assertEquals(normalizeNotification(base, "wrong-app"), null);
  assertEquals(
    normalizeNotification({ ...base, topic: "items" }, "12345"),
    null,
  );
  assertEquals(
    normalizeNotification({ ...base, resource: "/orders/../tenants" }, "12345"),
    null,
  );
});

Deno.test("deduplication key is stable and SHA-256 encoded", async () => {
  const key = await sha256Hex(
    "12345:67890:orders_v2:/orders/987654321:2026-10-05T18:00:00.000Z",
  );

  assert(/^[0-9a-f]{64}$/.test(key));
  assertEquals(
    key,
    await sha256Hex(
      "12345:67890:orders_v2:/orders/987654321:2026-10-05T18:00:00.000Z",
    ),
  );
});

Deno.test("rejects non-POST requests without touching the queue", async () => {
  const response = await handleRequest(
    new Request("https://example.test", {
      method: "GET",
    }),
  );

  assertEquals(response.status, 405);
});

Deno.test("requires the callback capability path", async () => {
  assertEquals(
    await matchesCapabilityPath(
      "/functions/v1/mercadolivre-orders-webhook/wrong",
      "expected-secret",
    ),
    false,
  );
  assertEquals(
    await matchesCapabilityPath(
      "/functions/v1/mercadolivre-orders-webhook/expected-secret",
      "expected-secret",
    ),
    true,
  );
});

import { describe, expect, it } from "vitest";
import { makeTestApp } from "./testApp.js";

const validPayload = {
  source: "linkedin",
  externalThreadId: "33333333-3333-4333-8333-333333333333",
  rawUrl: "https://www.linkedin.com/messaging/thread/123",
  title: "Chat with Ada",
  person: {
    fullName: "Ada Lovelace",
    linkedinUrl: "https://www.linkedin.com/in/ada",
    company: "Analytical Engines Ltd",
    roleTitle: "Founder",
  },
  messages: [
    {
      sourceMessageId: "msg-1",
      senderName: "Ada Lovelace",
      senderType: "contact",
      body: "Hello from LinkedIn",
      sentAt: "2026-01-01T12:00:00.000Z",
      messageOrder: 0,
      metadata: { importedFrom: "test" },
    },
  ],
};

describe("conversation import", () => {
  it("validates payloads", async () => {
    const app = await makeTestApp();
    const response = await app.inject({
      method: "POST",
      url: "/api/conversations/import",
      payload: { source: "linkedin", messages: [] },
    });
    await app.close();

    expect(response.statusCode).toBe(400);
  });

  it("stores a conversation and messages through the service boundary", async () => {
    const app = await makeTestApp();
    const importResponse = await app.inject({
      method: "POST",
      url: "/api/conversations/import",
      payload: validPayload,
    });

    expect(importResponse.statusCode).toBe(201);
    expect(importResponse.json().importedMessageCount).toBe(1);

    const getResponse = await app.inject({
      method: "GET",
      url: `/api/conversations/${validPayload.externalThreadId}`,
    });
    await app.close();

    expect(getResponse.statusCode).toBe(200);
    expect(getResponse.json().messages).toHaveLength(1);
  });
});

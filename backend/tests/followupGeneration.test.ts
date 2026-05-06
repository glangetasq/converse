import { describe, expect, it } from "vitest";
import { makeTestApp } from "./testApp.js";

describe("follow-up generation", () => {
  it("exposes a placeholder endpoint", async () => {
    const app = await makeTestApp();
    const response = await app.inject({
      method: "POST",
      url: "/api/followups/generate",
      payload: {
        conversationId: "44444444-4444-4444-8444-444444444444",
        tone: "warm",
        targetLength: "short",
      },
    });
    await app.close();

    expect(response.statusCode).toBe(200);
    expect(response.json()).toMatchObject({ status: "placeholder", generatedText: "" });
  });
});

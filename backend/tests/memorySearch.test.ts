import { describe, expect, it } from "vitest";
import { makeTestApp } from "./testApp.js";

describe("memory search", () => {
  it("exposes a placeholder endpoint", async () => {
    const app = await makeTestApp();
    const response = await app.inject({
      method: "POST",
      url: "/api/memory/search",
      payload: { query: "What does this person care about?", limit: 5 },
    });
    await app.close();

    expect(response.statusCode).toBe(200);
    expect(response.json()).toMatchObject({ status: "placeholder", results: [] });
  });
});

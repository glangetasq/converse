import { describe, expect, it } from "vitest";
import { makeTestApp } from "./testApp.js";

describe("health", () => {
  it("returns ok", async () => {
    const app = await makeTestApp();
    const response = await app.inject({ method: "GET", url: "/health" });
    await app.close();

    expect(response.statusCode).toBe(200);
    expect(response.json()).toEqual({ status: "ok" });
  });
});

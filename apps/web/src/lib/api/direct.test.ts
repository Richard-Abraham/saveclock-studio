import { http } from "msw";
import { describe, expect, it } from "vitest";

import { json, server } from "../../../tests/msw";
import { createDirectApi, directApiBase } from "./direct";
import { fetchHealth } from "./endpoints";

describe("direct API origin (OQ-26 Branch B)", () => {
  it("defaults to the API's own localhost origin, without a trailing slash", () => {
    expect(directApiBase()).toBe("http://localhost:8000");
  });

  it("is a client that talks to that origin, not to the web origin", async () => {
    server.use(http.get("http://localhost:8000/api/v1/health/ready", () => json.ready()));
    expect(await fetchHealth(createDirectApi())).toEqual({ kind: "ok" });
  });
});

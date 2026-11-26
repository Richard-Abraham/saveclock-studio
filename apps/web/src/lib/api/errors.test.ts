import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "../../../tests/msw";
import { createApi, call } from "./client";
import { ApiError } from "./errors";

const api = createApi("http://localhost:3000");

async function failure(run: () => Promise<unknown>): Promise<ApiError> {
  try {
    await run();
  } catch (cause) {
    if (cause instanceof ApiError) return cause;
    throw cause;
  }
  throw new Error("expected an ApiError");
}

describe("API error mapping", () => {
  it("turns the error envelope into a typed ApiError", async () => {
    server.use(
      http.get("http://localhost:3000/api/v1/settings", () =>
        HttpResponse.json(
          {
            error: {
              code: "forbidden",
              message: "x",
              details: { reason: "origin_mismatch" },
              request_id: "abc",
              doc_url: null,
            },
          },
          { status: 403 },
        ),
      ),
    );
    const error = await failure(() => call(() => api.GET("/api/v1/settings")));
    expect(error.code).toBe("forbidden");
    expect(error.requestId).toBe("abc");
    expect(error.status).toBe(403);
    expect(error.details).toEqual({ reason: "origin_mismatch" });
    expect(error.enveloped).toBe(true);
  });

  it("maps a non-JSON 502 to upstream_unavailable, not enveloped", async () => {
    server.use(
      http.get(
        "http://localhost:3000/api/v1/settings",
        () =>
          new HttpResponse("<html>Bad Gateway</html>", {
            status: 502,
            headers: { "content-type": "text/html" },
          }),
      ),
    );
    const error = await failure(() => call(() => api.GET("/api/v1/settings")));
    expect(error.code).toBe("upstream_unavailable");
    expect(error.status).toBe(502);
    expect(error.requestId).toBeNull();
    expect(error.enveloped).toBe(false);
  });

  it("maps a code the web does not know to internal_error", async () => {
    server.use(
      http.get("http://localhost:3000/api/v1/settings", () =>
        HttpResponse.json(
          { error: { code: "brand_new_code", message: "x", request_id: "abc" } },
          { status: 400 },
        ),
      ),
    );
    const error = await failure(() => call(() => api.GET("/api/v1/settings")));
    expect(error.code).toBe("internal_error");
    expect(error.requestId).toBe("abc");
  });

  it("maps a network failure to status 0", async () => {
    server.use(http.get("http://localhost:3000/api/v1/settings", () => HttpResponse.error()));
    const error = await failure(() => call(() => api.GET("/api/v1/settings")));
    expect(error.code).toBe("upstream_unavailable");
    expect(error.status).toBe(0);
  });
});

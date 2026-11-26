import { afterEach, describe, expect, it, vi } from "vitest";

import { readServerEnv } from "./server-env";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("readServerEnv", () => {
  it("uses the compose defaults when nothing is set", () => {
    vi.stubEnv("API_INTERNAL_URL", undefined);
    vi.stubEnv("ALLOWED_HOSTS", undefined);
    expect(readServerEnv()).toEqual({ apiOrigin: "http://api:8000", allowedHosts: ["localhost"] });
  });

  it("derives the origin (no path) from API_INTERNAL_URL and splits the host list", () => {
    vi.stubEnv("API_INTERNAL_URL", "http://127.0.0.1:8000/api/v1");
    vi.stubEnv("ALLOWED_HOSTS", "localhost,api");
    expect(readServerEnv()).toEqual({ apiOrigin: "http://127.0.0.1:8000", allowedHosts: ["localhost", "api"] });
  });

  it("rejects a malformed URL at startup", () => {
    vi.stubEnv("API_INTERNAL_URL", "not a url");
    expect(() => readServerEnv()).toThrow();
  });
});

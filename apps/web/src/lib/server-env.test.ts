import { describe, expect, it } from "vitest";

import { readServerEnv } from "./server-env";

describe("readServerEnv", () => {
  it("uses the compose defaults when nothing is set", () => {
    expect(readServerEnv({ API_INTERNAL_URL: undefined, ALLOWED_HOSTS: undefined })).toEqual({
      apiOrigin: "http://api:8000",
      allowedHosts: ["localhost"],
    });
  });

  it("derives the origin (no path) from API_INTERNAL_URL and splits the host list", () => {
    expect(
      readServerEnv({ API_INTERNAL_URL: "http://127.0.0.1:8000/api/v1", ALLOWED_HOSTS: "localhost,api" }),
    ).toEqual({ apiOrigin: "http://127.0.0.1:8000", allowedHosts: ["localhost", "api"] });
  });

  it("rejects a malformed URL at startup", () => {
    expect(() => readServerEnv({ API_INTERNAL_URL: "not a url", ALLOWED_HOSTS: undefined })).toThrow();
  });
});

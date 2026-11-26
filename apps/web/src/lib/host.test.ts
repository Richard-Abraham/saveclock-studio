import { describe, expect, it } from "vitest";

import { hostname, isAllowedHost, parseAllowedHosts } from "./host";

const ALLOWED = ["localhost", "127.0.0.1"];

describe("isAllowedHost", () => {
  it.each([
    ["localhost:3000", true],
    ["localhost", true],
    ["LOCALHOST:3000", true],
    ["localhost.:3000", true],
    ["127.0.0.1:3000", true],
    ["evil.example", false],
    ["evil.example:3000", false],
    ["localhost.evil.example", false],
    ["127.0.0.1.evil.example:3000", false],
    ["api:8000", false],
    ["", false],
    ["   ", false],
    [null, false],
    [undefined, false],
  ])("%s -> %s", (host, expected) => {
    expect(isAllowedHost(host, ALLOWED)).toBe(expected);
  });

  it("handles a bracketed IPv6 host", () => {
    expect(isAllowedHost("[::1]:3000", ["::1"])).toBe(true);
    expect(isAllowedHost("[::2]:3000", ["::1"])).toBe(false);
  });
});

describe("helpers", () => {
  it("strips the port and trailing dot", () => {
    expect(hostname("Localhost.:3000")).toBe("localhost");
    expect(hostname("[::1]:8000")).toBe("::1");
  });

  it("parses the allowlist csv", () => {
    expect(parseAllowedHosts(" localhost, 127.0.0.1 ,,")).toEqual(["localhost", "127.0.0.1"]);
  });
});

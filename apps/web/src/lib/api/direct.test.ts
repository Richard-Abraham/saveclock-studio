import { describe, expect, it } from "vitest";

import { directApiBase } from "./direct";

describe("direct API origin (OQ-26 Branch B)", () => {
  it("defaults to the API's own localhost origin, without a trailing slash", () => {
    expect(directApiBase()).toBe("http://localhost:8000");
  });
});

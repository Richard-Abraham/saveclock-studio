import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, vi } from "vitest";

import { server } from "./msw";

// Next's request-scoped helpers have no request in a unit test.
vi.mock("next/server", () => ({ connection: () => Promise.resolve() }));

// At import time, not in beforeAll: clients created at module level must capture the patched fetch.
server.listen({ onUnhandledFrame: "error" });
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => {
  server.close();
});

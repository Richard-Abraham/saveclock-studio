import { z } from "zod";

import { parseAllowedHosts } from "./host";

/** Server-only environment (STANDARDS §3): read once, validated with Zod, never sent to the browser. */
const schema = z.object({
  API_INTERNAL_URL: z.url().default("http://api:8000/api/v1"),
  ALLOWED_HOSTS: z.string().default("localhost"),
  // plan 009: the throwaway dev-driver page exists only when this is "1" or "true" (empty = off)
  DEV_DRIVER: z.string().default(""),
});

export type ServerEnv = {
  /** Scheme + host + port of the API, no path: the generated paths already start with /api/v1. */
  apiOrigin: string;
  allowedHosts: string[];
  /** Whether the dev-only driver page (/dev) is served. Off by default; never a NEXT_PUBLIC_ value. */
  devDriver: boolean;
};

export function readServerEnv(): ServerEnv {
  const parsed = schema.parse(process.env);
  return {
    apiOrigin: new URL(parsed.API_INTERNAL_URL).origin,
    allowedHosts: parseAllowedHosts(parsed.ALLOWED_HOSTS),
    devDriver: parsed.DEV_DRIVER === "1" || parsed.DEV_DRIVER === "true",
  };
}

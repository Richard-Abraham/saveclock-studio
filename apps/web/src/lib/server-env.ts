import { z } from "zod";

import { parseAllowedHosts } from "./host";

/** Server-only environment (STANDARDS §3): read once, validated with Zod, never sent to the browser. */
const schema = z.object({
  API_INTERNAL_URL: z.url().default("http://api:8000/api/v1"),
  ALLOWED_HOSTS: z.string().default("localhost"),
});

export type ServerEnv = {
  /** Scheme + host + port of the API, no path: the generated paths already start with /api/v1. */
  apiOrigin: string;
  allowedHosts: string[];
};

export function readServerEnv(): ServerEnv {
  const parsed = schema.parse(process.env);
  return {
    apiOrigin: new URL(parsed.API_INTERNAL_URL).origin,
    allowedHosts: parseAllowedHosts(parsed.ALLOWED_HOSTS),
  };
}

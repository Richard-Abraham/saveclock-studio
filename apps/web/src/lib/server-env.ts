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

type RawEnv = { API_INTERNAL_URL: string | undefined; ALLOWED_HOSTS: string | undefined };

export function readServerEnv(
  raw: RawEnv = {
    API_INTERNAL_URL: process.env.API_INTERNAL_URL,
    ALLOWED_HOSTS: process.env.ALLOWED_HOSTS,
  },
): ServerEnv {
  const parsed = schema.parse({
    API_INTERNAL_URL: raw.API_INTERNAL_URL || undefined,
    ALLOWED_HOSTS: raw.ALLOWED_HOSTS || undefined,
  });
  return {
    apiOrigin: new URL(parsed.API_INTERNAL_URL).origin,
    allowedHosts: parseAllowedHosts(parsed.ALLOWED_HOSTS),
  };
}

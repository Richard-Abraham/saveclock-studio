import type { paths } from "@saveclock/contracts";
import createClient from "openapi-fetch";

import { ApiError, networkError, toApiError } from "./errors";

/**
 * The one data boundary (STANDARDS §3). Components never call `fetch`; they call these functions.
 * `baseUrl` is "" in the browser (relative /api/v1/... through the Next rewrite) and the API origin
 * on the server.
 */
export function createApi(baseUrl: string, init: { noStore?: boolean } = {}) {
  return createClient<paths>({ baseUrl, ...(init.noStore ? { cache: "no-store" as const } : {}) });
}

export type Api = ReturnType<typeof createApi>;

type Settled<T> = { data?: T; error?: unknown; response: Response };

/** Run a request and return its data, or throw an `ApiError` (network failures included). */
export async function call<T>(run: () => Promise<Settled<T>>): Promise<T> {
  let result: Settled<T>;
  try {
    result = await run();
  } catch (cause) {
    throw networkError(cause);
  }
  if (result.response.ok && result.data !== undefined) return result.data;
  throw toApiError(result.error, result.response.status);
}

export { ApiError };

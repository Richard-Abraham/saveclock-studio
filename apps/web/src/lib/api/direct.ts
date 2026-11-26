import { apiOrigin } from "../config";

/**
 * Base URL for the two capabilities that cannot go through the Next rewrite: SSE and the 100 MB
 * upload (OQ-26: the rewrite cuts request bodies at 10 MB). Ordinary JSON calls stay relative.
 * Neither consumer exists yet; they land in T-2.x and must use this, not a relative URL.
 */
export function directApiBase(): string {
  return apiOrigin.replace(/\/$/, "");
}

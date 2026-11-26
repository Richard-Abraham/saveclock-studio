import { z } from "zod";

/** The only values the browser bundle reads from the environment, and both are public. The one place
 *  each origin default lives; `make images` passes the real values as build args (never defaults). */
export const appOrigin = z.url().default("http://localhost:3000").parse(process.env.NEXT_PUBLIC_APP_ORIGIN);

/** OQ-26 Branch B: the API's own localhost origin, used by the browser for SSE and uploads. */
export const apiOrigin = z.url().default("http://localhost:8000").parse(process.env.NEXT_PUBLIC_API_ORIGIN);

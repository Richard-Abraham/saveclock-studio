import { z } from "zod";

/** The only values the browser bundle reads from the environment, and both are public. */
export const appOrigin = z.url().parse(process.env.NEXT_PUBLIC_APP_ORIGIN ?? "http://localhost:3000");

/** OQ-26 Branch B: the API's own localhost origin, used by the browser for SSE and uploads. */
export const apiOrigin = z.url().parse(process.env.NEXT_PUBLIC_API_ORIGIN ?? "http://localhost:8000");

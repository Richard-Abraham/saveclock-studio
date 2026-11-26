import { z } from "zod";

/** The only value the browser bundle reads from the environment, and it is public. */
export const appOrigin = z.url().parse(process.env.NEXT_PUBLIC_APP_ORIGIN ?? "http://localhost:3000");

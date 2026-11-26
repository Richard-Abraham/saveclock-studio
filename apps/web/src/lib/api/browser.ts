import { createApi } from "./client";

/** Relative URLs: the browser talks to the API only through the single origin (Next rewrite). */
export const browserApi = createApi("");

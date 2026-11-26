import { NextResponse, type NextRequest } from "next/server";

import { isAllowedHost } from "@/lib/host";
import { readServerEnv } from "@/lib/server-env";

const { allowedHosts } = readServerEnv();

/**
 * Host allowlist for every page (SEC-166, plan 002 W14). The rewrite to the API has its own `has`
 * condition on Host; the API checks Host again at its own edge. Never reads the request body.
 */
export function proxy(request: NextRequest): Response {
  if (isAllowedHost(request.headers.get("host"), allowedHosts)) return NextResponse.next();
  return new Response("Host not allowed", {
    status: 403,
    headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" },
  });
}

export const config = {
  // Pages and /healthz only. NOT /api (a proxy touching /api request bodies applies a default
  // body-size limit that would break the 100 MB upload; OQ-26), and not static assets.
  matcher: ["/((?!api/|_next/static|_next/image|favicon\\.ico).*)"],
};

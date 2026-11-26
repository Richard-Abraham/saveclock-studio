import { NextResponse, type NextRequest } from "next/server";

import { isAllowedHost } from "@/lib/host";
import { readServerEnv } from "@/lib/server-env";

const { allowedHosts } = readServerEnv();

/**
 * Host allowlist for every web route, /api included (SEC-166, plan 002 W14): one rule, one verdict.
 * The API checks Host again at its own edge. Never reads the request body.
 */
export function proxy(request: NextRequest): Response {
  if (isAllowedHost(request.headers.get("host"), allowedHosts)) return NextResponse.next();
  return new Response("Host not allowed. Use http://localhost:3000 (not 127.0.0.1 or another name).", {
    status: 403,
    headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" },
  });
}

export const config = {
  // Every route including /api (JSON through the rewrite; uploads go straight to the API since OQ-26
  // Branch B, so the proxy's 10 MB body buffer no longer matters), but not static assets.
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico).*)"],
};

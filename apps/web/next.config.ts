import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

import { apiOrigin } from "./src/lib/config";
import { readServerEnv } from "./src/lib/server-env";

// shortcut: Next bakes `rewrites()` into the build, so API_INTERNAL_URL and ALLOWED_HOSTS are read
// when the image is built (their defaults match compose); upgrade to a runtime proxy only if the
// api ever moves off http://api:8000.
const { apiOrigin: apiInternalOrigin } = readServerEnv();

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  // Report-only soak (plan 002 W8); the nonce-based strict policy is Phase 3. No HSTS on purpose.
  {
    key: "Content-Security-Policy-Report-Only",
    value:
      `default-src 'self'; connect-src 'self' ${apiOrigin}; img-src 'self' data:; ` +
      "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'",
  },
];

const config: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: join(dirname(fileURLToPath(import.meta.url)), "../.."),
  poweredByHeader: false,
  images: { unoptimized: true },
  headers() {
    return Promise.resolve([{ source: "/:path*", headers: securityHeaders }]);
  },
  rewrites() {
    return Promise.resolve([
      {
        source: "/api/:path*",
        destination: `${apiInternalOrigin}/api/:path*`,
      },
    ]);
  },
};

export default config;

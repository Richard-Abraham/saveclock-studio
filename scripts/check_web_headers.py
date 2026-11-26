"""Response headers of the web shell and of the API through the rewrite (SEC-111, plan 002 Step 5).

Usage: python3 scripts/check_web_headers.py [--web http://127.0.0.1:3000]
Run against the running stack. Stdlib only.
"""

import argparse
import http.client
import sys
from urllib.parse import urlsplit

COMMON = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
}
CSP = "content-security-policy-report-only"
FORBIDDEN = ("strict-transport-security", "access-control-allow-origin")


def headers_of(base: str, path: str) -> dict[str, str]:
    parts = urlsplit(base)
    conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=15)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        response.read()
        return {k.lower(): v for k, v in response.getheaders()}
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", default="http://localhost:3000")
    web = parser.parse_args().web
    problems: list[str] = []

    for path in ("/", "/settings", "/healthz"):
        got = headers_of(web, path)
        for name, value in COMMON.items():
            if got.get(name) != value:
                problems.append(f"{path}: {name} is {got.get(name)!r}, want {value!r}")
        csp = got.get(CSP, "")
        if "default-src 'self'" not in csp or "frame-ancestors 'none'" not in csp:
            problems.append(f"{path}: {CSP} is {csp!r}")
        if "content-security-policy" in got:
            problems.append(f"{path}: an enforcing Content-Security-Policy is set (Phase 3, W8)")
        for name in FORBIDDEN:
            if name in got:
                problems.append(f"{path}: {name} must not be present")

    # the rewrite must not strip what the API sets
    api = headers_of(web, "/api/v1/health/live")
    for name, value in {**COMMON, "cache-control": "private, no-store"}.items():
        if api.get(name) != value:
            problems.append(f"/api/v1/health/live via web: {name} is {api.get(name)!r}, want {value!r}")
    for name in FORBIDDEN:
        if name in api:
            problems.append(f"/api/v1/health/live via web: {name} must not be present")

    for line in problems:
        print(f"HEADERS FAIL {line}")
    if problems:
        return 1
    print("HEADERS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

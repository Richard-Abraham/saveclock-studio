"""Smoke test of the web shell against the RUNNING stack (plan 002 Step 8). Stdlib only.

Usage: python3 scripts/smoke_web.py [--web http://localhost:3000] [--api http://localhost:8000]
                                    [--project-title TITLE]
Retries for up to 60 s while the stack comes up. Prints one PASS/FAIL line per check: the pages, the
one Host rule, CORS on the API origin, and the response headers of the web shell (SEC-111).
"""

import argparse
import json
import sys
import time

from web_http import fetch, preflight

EMPTY_COPY = "No videos yet. Choose a song to make your first one."
APP_ORIGIN = "http://localhost:3000"
SHELL_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
}
FORBIDDEN_HEADERS = ("strict-transport-security", "access-control-allow-origin")


def wait_for(base: str, path: str, seconds: int = 60) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            if fetch(base, "GET", path)[0] == 200:
                return True
        except OSError:
            pass
        time.sleep(2)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", default="http://localhost:3000")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--project-title", default=None, help="expect this seeded project on /")
    args = parser.parse_args()
    web, api = args.web, args.api

    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'} {label}" + (f" ({detail})" if detail and not ok else ""))
        if not ok:
            failures.append(label)

    if not wait_for(web, "/healthz"):
        print("FAIL the web server did not answer /healthz within 60 s")
        return 1

    status, _, body = fetch(web, "GET", "/")
    check("GET / is 200", status == 200, str(status))
    check("/ contains Projects", "Projects" in body)
    if args.project_title:
        check(f"/ lists the seeded project {args.project_title!r}", args.project_title in body)
    else:
        check("/ shows the empty-state copy", EMPTY_COPY in body)
    status, _, body = fetch(web, "GET", "/settings")
    check("GET /settings is 200", status == 200, str(status))
    check("/settings contains Performance", "Performance" in body)
    check("GET /healthz is 200", fetch(web, "GET", "/healthz")[0] == 200)

    status, _, body = fetch(web, "GET", "/api/v1/health/live")
    check(
        "GET /api/v1/health/live through the rewrite is 200 ok",
        status == 200 and json.loads(body) == {"status": "ok"},
        f"{status} {body[:80]}",
    )
    status = fetch(web, "POST", "/api/v1/health/live", {"Origin": "http://evil.example"})[0]
    check("POST through the rewrite with a foreign Origin is 403", status == 403, str(status))
    status = fetch(web, "POST", "/api/v1/health/live")[0]
    check("POST through the rewrite with no Origin is not 403", status != 403, str(status))

    # One Host rule for pages and /api alike: localhost in any case or with a trailing dot passes; a
    # foreign host and 127.0.0.1 (a different origin from the CORS allow-list's) are refused.
    for path in ("/", "/settings", "/healthz", "/api/v1/health/live"):
        for host in ("localhost:3000", "LOCALHOST:3000", "localhost.:3000"):
            status = fetch(web, "GET", path, {"Host": host})[0]
            check(f"Host {host} to {path} is 200", status == 200, str(status))
        for host in ("evil.example", "127.0.0.1:3000"):
            status = fetch(web, "GET", path, {"Host": host})[0]
            check(f"Host {host} to {path} is 403", status == 403, str(status))
    status = fetch(api, "GET", "/api/v1/health/live", {"Host": "evil.example"})[0]
    check("foreign Host straight to the API is 403", status == 403, str(status))

    # Branch B (OQ-26): the browser calls the API origin directly; CORS allows only the app origin.
    check("CORS preflight from the app origin is allowed", preflight(api, APP_ORIGIN)[1] == APP_ORIGIN)
    check("CORS preflight from a foreign origin gets no Allow-Origin", preflight(api, "http://evil.example")[1] is None)

    # response headers: the shell's own, and the API's surviving the rewrite
    for path in ("/", "/settings", "/healthz"):
        got = fetch(web, "GET", path)[1]
        for name, value in SHELL_HEADERS.items():
            check(f"{path}: {name}", got.get(name) == value, f"{got.get(name)!r}, want {value!r}")
        csp = got.get("content-security-policy-report-only", "")
        check(f"{path}: report-only CSP", "default-src 'self'" in csp and "frame-ancestors 'none'" in csp, csp)
        check(f"{path}: no enforcing CSP", "content-security-policy" not in got)
        for name in FORBIDDEN_HEADERS:
            check(f"{path}: no {name}", name not in got)
    via = fetch(web, "GET", "/api/v1/health/live")[1]
    for name, value in {**SHELL_HEADERS, "cache-control": "private, no-store"}.items():
        check(f"/api via the rewrite: {name}", via.get(name) == value, f"{via.get(name)!r}, want {value!r}")
    for name in FORBIDDEN_HEADERS:
        check(f"/api via the rewrite: no {name}", name not in via)

    if failures:
        print(f"WEB SMOKE FAILED ({len(failures)}): " + "; ".join(failures))
        return 1
    print("WEB SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

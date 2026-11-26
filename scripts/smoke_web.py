"""Smoke test of the web shell against the RUNNING stack (plan 002 Step 8). Stdlib only.

Usage: python3 scripts/smoke_web.py [--web http://127.0.0.1:3000] [--api http://127.0.0.1:8000]
                                    [--project-title TITLE]
Retries for up to 60 s while the stack comes up. Prints one PASS/FAIL line per check.
"""

import argparse
import http.client
import json
import sys
import time
from urllib.parse import urlsplit

EMPTY_COPY = "No videos yet. Choose a song to make your first one."


def request(base: str, method: str, path: str, headers: dict[str, str] | None = None) -> tuple[int, str]:
    parts = urlsplit(base)
    conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=15)
    try:
        conn.request(method, path, headers=headers or {})
        response = conn.getresponse()
        return response.status, response.read().decode("utf-8", "replace")
    finally:
        conn.close()


def wait_for(base: str, path: str, seconds: int = 60) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            if request(base, "GET", path)[0] == 200:
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

    status, body = request(web, "GET", "/")
    check("GET / is 200", status == 200, str(status))
    check("/ contains Projects", "Projects" in body)
    if args.project_title:
        check(f"/ lists the seeded project {args.project_title!r}", args.project_title in body)
    else:
        check("/ shows the empty-state copy", EMPTY_COPY in body)

    status, body = request(web, "GET", "/settings")
    check("GET /settings is 200", status == 200, str(status))
    check("/settings contains Performance", "Performance" in body)

    check("GET /healthz is 200", request(web, "GET", "/healthz")[0] == 200)

    status, body = request(web, "GET", "/api/v1/health/live")
    check("GET /api/v1/health/live through the rewrite is 200 ok", status == 200 and json.loads(body) == {"status": "ok"}, f"{status} {body[:80]}")

    evil = {"Origin": "http://evil.example"}
    status, _ = request(web, "POST", "/api/v1/health/live", evil)
    check("POST through the rewrite with a foreign Origin is 403", status == 403, str(status))
    status, _ = request(web, "POST", "/api/v1/health/live")
    check("POST through the rewrite with no Origin is not 403", status != 403, str(status))

    # One Host rule for pages and /api alike: localhost in any case or with a trailing dot passes; a
    # foreign host and 127.0.0.1 (a different origin from the CORS allow-list's) are refused.
    foreign = {"Host": "evil.example"}
    for path in ("/", "/settings", "/healthz", "/api/v1/health/live"):
        for host in ("localhost:3000", "LOCALHOST:3000", "localhost.:3000"):
            status = request(web, "GET", path, {"Host": host})[0]
            check(f"Host {host} to {path} is 200", status == 200, str(status))
        for host in ("evil.example", "127.0.0.1:3000"):
            status = request(web, "GET", path, {"Host": host})[0]
            check(f"Host {host} to {path} is 403", status == 403, str(status))
    check("foreign Host straight to the API is 403", request(api, "GET", "/api/v1/health/live", foreign)[0] == 403)

    # Branch B (OQ-26): the browser calls the API origin directly; CORS allows only the app origin.
    def allow_origin(origin: str) -> str | None:
        parts = urlsplit(api)
        conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=15)
        conn.request("OPTIONS", "/api/v1/health/live", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
        response = conn.getresponse()
        response.read()
        conn.close()
        return response.getheader("access-control-allow-origin")

    check("CORS preflight from the app origin is allowed", allow_origin("http://localhost:3000") == "http://localhost:3000")
    check("CORS preflight from a foreign origin gets no Allow-Origin", allow_origin("http://evil.example") is None)

    if failures:
        print(f"WEB SMOKE FAILED ({len(failures)}): " + "; ".join(failures))
        return 1
    print("WEB SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Stack smoke through the web origin (plan 003 Step 2b/2c, re-pointed by plan 008). Stdlib only.

Usage: python3 scripts/smoke_stack.py [--web http://localhost:3000] [--api http://127.0.0.1:8000]
Env (optional, enables the log checks): COMPOSE (the compose command, set by make).

One PASS/FAIL line per check, ending in `STACK SMOKE OK`. It creates one empty project and deletes
it again (`DELETE /projects/{id}` is part of the smoke), so it leaves no residue. The four-hop job
chain is covered by the real-subprocess tests (test_draft_e2e.py, test_render_e2e.py).
"""

import argparse
import http.client
import json
import os
import re
import shlex
import subprocess
import sys
import time
from urllib.parse import urlsplit

SERVICES = ("api", "worker", "worker-maint", "web")


def call(
    base: str, method: str, path: str, headers: dict[str, str] | None = None, body: bytes | None = None
) -> tuple[int, dict[str, str], bytes]:
    parts = urlsplit(base)
    conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=20)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()
    finally:
        conn.close()


def create_project(base: str, origin: str) -> tuple[int, dict[str, str], bytes]:
    headers = {"Origin": origin, "Content-Type": "application/json"}
    return call(base, "POST", "/api/v1/projects", headers, b"{}")


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def service_logs(compose: str, service: str) -> str:
    """The service's log, without podman-compose's colour codes."""
    out = subprocess.run(  # noqa: S603 - the compose command comes from make
        [*shlex.split(compose), "logs", "--no-log-prefix", service],
        capture_output=True, text=True, check=False,
    )
    return ANSI.sub("", out.stdout + out.stderr)


def json_lines(text: str) -> tuple[list[dict], int]:
    """(parsed lines that start with `{`, count of such lines that do not parse)."""
    good, bad = [], 0
    for line in text.splitlines():
        if line.startswith("{"):
            try:
                good.append(json.loads(line))
            except ValueError:
                bad += 1
    return good, bad


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", default="http://localhost:3000")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    web, api = args.web, args.api
    origin = web  # the app origin the browser would send
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'} {label}" + (f" ({detail})" if detail and not ok else ""))
        if not ok:
            failures.append(label)

    status, hdrs, body = create_project(web, origin)
    check("POST /projects through the web origin is 201", status == 201, f"{status} {body[:80]!r}")
    if status != 201:
        print("STACK SMOKE FAILED (no project)")
        return 1
    project_id, request_id = json.loads(body)["id"], hdrs.get("x-request-id", "")
    check("the response carries X-Request-Id", bool(request_id))

    status, _, body = call(web, "GET", "/api/v1/projects")
    items = json.loads(body)["items"] if status == 200 else []
    check("GET /projects lists the new project", any(p["id"] == project_id for p in items))
    status, _, _ = call(web, "GET", "/")
    check("the web shell page is 200", status == 200)

    deadline = time.monotonic() + 60
    tuning = None
    while time.monotonic() < deadline:
        status, _, body = call(web, "GET", "/api/v1/settings")
        tuning = json.loads(body).get("tuning") if status == 200 else None
        if tuning:
            break
        time.sleep(2)
    check("GET /settings shows tuning with heavy >= 1 (worker heartbeat)", bool(tuning) and tuning["heavy"] >= 1)

    for where, base in (("through :web", web), ("straight to the API", api)):
        status = create_project(base, "http://evil.example")[0]
        check(f"POST with a foreign Origin {where} is 403", status == 403, str(status))
    check(
        "foreign Host to the API is 403",
        call(api, "GET", "/api/v1/health/live", {"Host": "evil.example"})[0] == 403,
    )
    check("foreign Host to the web shell is 403", call(web, "GET", "/", {"Host": "evil.example"})[0] == 403)
    check(
        "foreign Host to the web shell's /api is not 200",
        call(web, "GET", "/api/v1/health/live", {"Host": "evil.example"})[0] != 200,
    )

    status, dhdrs, _ = call(web, "DELETE", f"/api/v1/projects/{project_id}", {"Origin": origin})
    delete_request_id = dhdrs.get("x-request-id", "")
    check("DELETE /projects/{id} is 202", status == 202, str(status))
    status, _, body = call(web, "GET", "/api/v1/projects")
    items = json.loads(body)["items"] if status == 200 else []
    check("the deleted project is gone from the list", all(p["id"] != project_id for p in items))

    compose = os.environ.get("COMPOSE")
    if compose:
        logs = {svc: service_logs(compose, svc) for svc in SERVICES}
        lines = {svc: json_lines(text) for svc, text in logs.items()}
        check("every JSON-looking log line parses", all(bad == 0 for _, bad in lines.values()))
        # SEC-123: the request id of the DELETE (it enqueues the purge, so the api logs `job.enqueued`)
        api_hit = any(rec.get("request_id") == delete_request_id for rec in lines["api"][0])
        check("the DELETE request id is in the api log", api_hit)
        secrets = [
            ln.split("=", 1)[1] for ln in open(".env").read().splitlines()  # noqa: SIM115
            if ln.split("=", 1)[0].endswith(("PASSWORD", "_KEY")) and "=" in ln and len(ln.split("=", 1)[1]) >= 8
        ]
        leaked = sum(1 for text in logs.values() for s in secrets if s in text)
        check(f"no .env secret value appears in the logs ({leaked} matches)", leaked == 0)
    else:
        print("SKIPPED log checks (COMPOSE not set)")

    if failures:
        print(f"STACK SMOKE FAILED ({len(failures)}): " + "; ".join(failures))
        return 1
    print("STACK SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

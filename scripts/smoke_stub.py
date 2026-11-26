"""Stub-job smoke through the web origin (plan 003 Step 2b/2c). Stdlib only.

Usage: python3 scripts/smoke_stub.py [--seed] [--web http://localhost:3000] [--api http://127.0.0.1:8000]
Env (optional, enables the log checks): CONTAINER, PROJECT (compose project name).

--seed: print `already seeded` when GET /projects already has items, otherwise run one stub job
(sleep 0) and print the project id. Without --seed: the full smoke, one PASS/FAIL line per check,
ending in `STUB SMOKE OK`. Every check reads only what the stack serves; nothing touches the database.
"""

import argparse
import http.client
import json
import os
import subprocess
import sys
import time
from urllib.parse import urlsplit
from uuid import UUID

HOPS = ("analysis", "fetch", "render", "maintenance")
STAGE_SERVICES = {"analysis": "worker", "fetch": "worker", "render": "worker", "maintenance": "worker-maint"}


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


def post_job(web: str, sleep_s: int, origin: str, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
    h = {"Origin": origin, "Content-Type": "application/json", **(headers or {})}
    return call(web, "POST", "/api/v1/_stub/jobs", h, json.dumps({"sleep_s": sleep_s}).encode())


def wait_chain(web: str, job_id: str, seconds: int = 60) -> dict | None:
    end = time.monotonic() + seconds
    chain: dict = {}
    while time.monotonic() < end:
        status, _, body = call(web, "GET", f"/api/v1/_stub/jobs/{job_id}")
        if status == 200:
            chain = json.loads(body)
            states = {h["queue"]: h["state"] for h in chain["hops"]}
            if all(states.get(q) == "ok" for q in HOPS):
                return chain
        time.sleep(1)
    return None


def service_logs(container: str, project: str, service: str) -> str:
    out = []
    for label in ("io.podman.compose.project", "com.docker.compose.project"):
        ids = subprocess.run(  # noqa: S603 - fixed argument list
            [container, "ps", "-q", "--filter", f"label=com.docker.compose.service={service}",
             "--filter", f"label={label}={project}"],
            capture_output=True, text=True, check=False,
        ).stdout.split()
        for cid in ids:
            logs = subprocess.run([container, "logs", cid], capture_output=True, text=True, check=False)  # noqa: S603
            out.append(logs.stdout + logs.stderr)
    return "\n".join(out)


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


def seed(web: str, origin: str) -> int:
    status, _, body = call(web, "GET", "/api/v1/projects")
    if status != 200:
        print(f"FAIL GET /projects is {status}")
        return 1
    if json.loads(body)["items"]:
        print("already seeded")
        return 0
    status, _, body = post_job(web, 0, origin)
    if status != 202:
        print(f"FAIL seed POST is {status}")
        return 1
    job = json.loads(body)
    if wait_chain(web, job["job_id"]) is None:
        print("FAIL seed job did not finish its four hops in 60 s")
        return 1
    print(f"seeded project {job['project_id']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", default="http://localhost:3000")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--propagation", action="store_true", help="also require the request id in the api and worker logs")
    args = parser.parse_args()
    web, api = args.web, args.api
    origin = web  # the app origin the browser would send
    if args.seed:
        return seed(web, origin)

    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'} {label}" + (f" ({detail})" if detail and not ok else ""))
        if not ok:
            failures.append(label)

    status, hdrs, body = post_job(web, 1, origin)
    check("POST a stub job through the web origin is 202", status == 202, f"{status} {body[:80]!r}")
    if status != 202:
        print("STUB SMOKE FAILED (no job)")
        return 1
    job = json.loads(body)
    job_id, project_id, request_id = job["job_id"], job["project_id"], hdrs.get("x-request-id", "")
    check("the response carries X-Request-Id", bool(request_id))
    UUID(job_id)

    chain = wait_chain(web, job_id)
    check("all four hops (analysis, fetch, render, maintenance) reach ok within 60 s", chain is not None)
    if chain:
        check("every hop reports a run time", all(h["run_ms"] is not None for h in chain["hops"]))

    expect = f"stub job {job_id}\n".encode()
    s1, _, b1 = call(web, "GET", f"/api/v1/_stub/jobs/{job_id}/download")
    check("download through :web is the literal stub body", s1 == 200 and b1 == expect, f"{s1} {b1[:60]!r}")
    s2, _, b2 = call(api, "GET", f"/api/v1/_stub/jobs/{job_id}/download")
    check("download straight from the API is the literal stub body", s2 == 200 and b2 == expect, f"{s2} {b2[:60]!r}")
    s3, _, b3 = call(web, "GET", f"/api/v1/_stub/jobs/{job_id}/download", {"Range": "bytes=0-3"})
    check("Range bytes=0-3 is 206 with `stub`", s3 == 206 and b3 == b"stub", f"{s3} {b3!r}")

    status, _, body = call(web, "GET", "/api/v1/projects")
    items = json.loads(body)["items"] if status == 200 else []
    mine = [p for p in items if p["id"] == project_id]
    check("GET /projects lists the job's project", len(mine) == 1)
    title = mine[0]["title"] if mine else None
    status, _, page = call(web, "GET", "/")
    check("the web shell page is 200", status == 200)
    if title:
        check(f"the web shell lists the project title {title!r}", title in page.decode("utf-8", "replace"))

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
        status = post_job(base, 0, "http://evil.example")[0]
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

    container, project = os.environ.get("CONTAINER"), os.environ.get("PROJECT")
    if container and project:
        logs = {svc: service_logs(container, project, svc) for svc in ("api", "worker", "worker-maint", "web")}
        lines = {svc: json_lines(text) for svc, text in logs.items()}
        check("every JSON-looking log line parses", all(bad == 0 for _, bad in lines.values()))
        if args.propagation:  # SEC-123; the app code does not propagate the id yet, so this FAILS today
            api_hit = any(rec.get("request_id") == request_id for rec in lines["api"][0])
            check("the request id is in the api log", api_hit)
            for stage in HOPS:
                svc = STAGE_SERVICES[stage]
                hit = any(
                    rec.get("request_id") == request_id
                    and rec.get("stage") == stage
                    and rec.get("event") == "job.finished"
                    for rec in lines[svc][0]
                )
                check(f"the request id reaches the {stage} hop's worker log", hit)
        else:
            print("NOT RUN request-id propagation (SEC-123): make smoke-propagation (it fails today, an open finding)")
        secrets = [
            ln.split("=", 1)[1] for ln in open(".env").read().splitlines()  # noqa: SIM115
            if ln.split("=", 1)[0].endswith(("PASSWORD", "_KEY")) and "=" in ln and len(ln.split("=", 1)[1]) >= 8
        ]
        leaked = sum(1 for text in logs.values() for s in secrets if s in text)
        check(f"no .env secret value appears in the logs ({leaked} matches)", leaked == 0)
    else:
        print("SKIPPED log checks (CONTAINER and PROJECT not set)")

    if failures:
        print(f"STUB SMOKE FAILED ({len(failures)}): " + "; ".join(failures))
        return 1
    print("STUB SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

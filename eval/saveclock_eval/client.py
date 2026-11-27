"""A thin REST client for the eval run (httpx only; nothing from the CLI package).

Same safety rule as the CLI (SEC-168): the base URL must be this machine, checked before any
transport exists; no redirect is followed; no `Origin`, cookie or credential is sent. Waits poll
every 0.5 s and are bounded by the server's own budgets (`saveclock.cli.waits` derives them from
`saveclock.config`: the constants, not copies).
"""

from __future__ import annotations

import time
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from saveclock.cli.waits import WAIT_DRAFT_S, WAIT_MODE_A_S, WAIT_RENDER_S

LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})
POLL_S = 0.5
PREFIX = "/api/v1"

# a seam for the tests: the whole wait runs without sleeping
sleep = time.sleep
now = time.monotonic

__all__ = ["WAIT_DRAFT_S", "WAIT_MODE_A_S", "WAIT_RENDER_S", "ApiFailure", "EvalClient", "Refused"]


class Refused(Exception):
    """The URL is not this machine, or the API answered with a redirect."""


class ApiFailure(Exception):
    def __init__(self, status: int, code: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(f"{status} {code}")
        self.status = status
        self.code = code
        self.details = details or {}


class WaitTimeout(Exception):
    pass


def check_base_url(url: str) -> str:
    try:
        parts = urllib.parse.urlsplit(url.strip())
        host = (parts.hostname or "").lower()
        parts.port  # noqa: B018 - raises ValueError on a bad port
    except ValueError as exc:
        raise Refused(f"not a usable URL: {url!r}") from exc
    if parts.scheme not in {"http", "https"} or parts.username is not None:
        raise Refused(f"refusing {url!r}: needs http(s) and no user name")
    if host not in LOOPBACK:
        raise Refused(f"refusing {host!r}: the eval talks only to this machine")
    return url.strip().rstrip("/")


class EvalClient:
    def __init__(self, base_url: str, *, transport: httpx.BaseTransport | None = None) -> None:
        self.base_url = check_base_url(base_url)  # before any transport exists
        self._http = httpx.Client(
            base_url=self.base_url, transport=transport, follow_redirects=False, trust_env=False,
            headers={"User-Agent": "saveclock-eval/1"},
            timeout=httpx.Timeout(30.0, read=120.0, write=300.0),
        )

    def close(self) -> None:
        self._http.close()

    def _call(self, method: str, path: str, **kw: Any) -> httpx.Response:  # noqa: ANN401
        resp = self._http.request(method, f"{PREFIX}{path}", **kw)
        if 300 <= resp.status_code < 400:  # noqa: PLR2004
            raise Refused("redirect refused")
        if resp.status_code >= 400:  # noqa: PLR2004
            resp.read()
            try:
                err = resp.json()["error"]
                raise ApiFailure(resp.status_code, str(err["code"]), err.get("details") or {})
            except (ValueError, KeyError, TypeError):
                raise ApiFailure(resp.status_code, "internal_error") from None
        return resp

    # --- the calls ---------------------------------------------------------------------
    def settings(self) -> dict[str, Any]:
        return dict(self._call("GET", "/settings").json())

    def create_project(self, title: str | None, options: dict[str, Any]) -> str:
        body: dict[str, Any] = {"options": options}
        if title:
            body["title"] = title
        return str(self._call("POST", "/projects", json=body).json()["id"])

    def upload(self, project_id: str, song: Path) -> None:
        def chunks() -> Any:  # noqa: ANN401 - a generator: the file is never read whole
            with song.open("rb") as fh:
                while chunk := fh.read(1 << 20):
                    yield chunk

        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(song.stat().st_size),
            "X-Filename": urllib.parse.quote(song.name, safe=""),
        }
        self._call("POST", f"/projects/{project_id}/song", content=chunks(), headers=headers)

    def project(self, project_id: str) -> dict[str, Any]:
        return dict(self._call("GET", f"/projects/{project_id}").json())

    def analysis(self, project_id: str) -> dict[str, Any]:
        return dict(self._call("GET", f"/projects/{project_id}/analysis").json())

    def plan(self, project_id: str) -> dict[str, Any]:
        return dict(self._call("GET", f"/projects/{project_id}/plan").json())

    def create_render(self, project_id: str) -> str:
        return str(self._call("POST", f"/projects/{project_id}/renders", json={}).json()["render_id"])

    def render(self, render_id: str) -> dict[str, Any]:
        return dict(self._call("GET", f"/renders/{render_id}").json())

    def request_mode_a(self, render_id: str) -> None:
        self._call("POST", f"/renders/{render_id}/mode-a")

    def download(self, render_id: str, kind: str, dest: Path) -> None:
        with self._http.stream("GET", f"{PREFIX}/renders/{render_id}/download", params={"kind": kind}) as r:
            self._check_stream(r)
            with dest.open("wb") as fh:
                for chunk in r.iter_bytes(1 << 20):
                    fh.write(chunk)

    def _check_stream(self, resp: httpx.Response) -> None:
        if 300 <= resp.status_code < 400:  # noqa: PLR2004
            raise Refused("redirect refused")
        if resp.status_code >= 400:  # noqa: PLR2004
            resp.read()
            raise ApiFailure(resp.status_code, "download_failed")

    def delete_project(self, project_id: str) -> None:
        self._call("DELETE", f"/projects/{project_id}")


def wait_until(
    fetch: Callable[[], Any], done: Callable[[Any], bool], *, timeout_s: float, poll_s: float = POLL_S
) -> tuple[Any, float]:
    """Poll `fetch` until `done(value)`; returns (value, seconds waited, client-observed).

    The wall time includes queueing and the poll step, so it is an upper bound of the stage time.
    """
    start = now()
    while True:
        value = fetch()
        if done(value):
            return value, now() - start
        if now() - start >= timeout_s:
            raise WaitTimeout(f"still not done after {timeout_s:.0f} s")
        sleep(poll_s)

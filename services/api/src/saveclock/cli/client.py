"""The one HTTP layer of the CLI (SEC-168).

The base URL is checked before any transport exists; a redirect is never followed; no `Origin`,
cookie or credential is ever sent (the API accepts a request without an `Origin`, and holds no
login). Every call goes through `ENDPOINTS`, keyed by OpenAPI operation id.
"""

import urllib.parse
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus
from typing import Any

import httpx

from saveclock.cli import __version__

PREFIX = "/api/v1"
ENDPOINTS: dict[str, tuple[str, str]] = {
    "create_project": ("POST", f"{PREFIX}/projects"),
    "list_projects": ("GET", f"{PREFIX}/projects"),
    "get_project": ("GET", f"{PREFIX}/projects/{{project_id}}"),
    "upload_song": ("POST", f"{PREFIX}/projects/{{project_id}}/song"),
    "get_analysis": ("GET", f"{PREFIX}/projects/{{project_id}}/analysis"),
    "get_plan": ("GET", f"{PREFIX}/projects/{{project_id}}/plan"),
    "patch_plan": ("PATCH", f"{PREFIX}/projects/{{project_id}}/plan"),
    "get_credits": ("GET", f"{PREFIX}/projects/{{project_id}}/credits"),
    "stream_events": ("GET", f"{PREFIX}/projects/{{project_id}}/events"),
    "create_render": ("POST", f"{PREFIX}/projects/{{project_id}}/renders"),
    "get_render": ("GET", f"{PREFIX}/renders/{{render_id}}"),
    "request_mode_a": ("POST", f"{PREFIX}/renders/{{render_id}}/mode-a"),
    "download_render": ("GET", f"{PREFIX}/renders/{{render_id}}/download"),
}
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

EXIT_API, EXIT_USAGE, EXIT_NETWORK = 1, 2, 3


class CliError(Exception):
    """Anything the CLI reports and exits on; `code` is what a script reads."""

    exit_code = EXIT_API

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        exit_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.request_id: str | None = None
        if exit_code is not None:
            self.exit_code = exit_code


class Refused(CliError):
    """The CLI will not do this (a host that is not this machine, a redirect, bad usage)."""

    def __init__(self, message: str, *, code: str = "refused", exit_code: int = EXIT_USAGE) -> None:
        super().__init__(code, message, exit_code=exit_code)


class NetworkError(CliError):
    exit_code = EXIT_NETWORK

    def __init__(self, message: str, *, code: str = "network_error") -> None:
        super().__init__(code, message)


class ApiError(CliError):
    def __init__(
        self, status: int, code: str, message: str, details: dict[str, Any], request_id: str | None
    ) -> None:
        super().__init__(code, message, details=details)
        self.status = status
        self.request_id = request_id


def check_base_url(url: str) -> str:
    """The URL when it points at this machine over http(s) with no userinfo; else `Refused`."""
    try:
        parts = urllib.parse.urlsplit(url.strip())
        host = (parts.hostname or "").lower()
        parts.port  # noqa: B018 - raises ValueError on a bad port
    except ValueError as exc:
        raise Refused(f"not a usable URL: {url!r}") from exc
    if parts.scheme not in {"http", "https"}:
        raise Refused(f"the API URL must be http or https, not {parts.scheme or 'empty'!r}")
    if parts.username is not None or parts.password is not None:
        raise Refused("the API URL must not carry a user name or password")
    if host not in LOOPBACK_HOSTS:
        raise Refused(
            f"refusing {host or 'an empty host'!r}: the CLI talks only to this machine "
            "(localhost, 127.0.0.1 or ::1)"
        )
    return url.strip().rstrip("/")


def valid_id(value: str) -> str:
    """A project or render id is a UUID; anything else never reaches a URL path."""
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise Refused(f"not an id: {value!r}") from exc


def _error_from(resp: httpx.Response) -> ApiError:
    body: Any = None
    try:
        body = resp.json()
    except ValueError:
        body = None
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict) and isinstance(err.get("code"), str):
        details = err.get("details")
        return ApiError(
            resp.status_code,
            err["code"],
            str(err.get("message") or ""),
            details if isinstance(details, dict) else {},
            err.get("request_id") if isinstance(err.get("request_id"), str) else None,
        )
    return ApiError(
        resp.status_code,
        "internal_error",
        f"HTTP {resp.status_code} without an error envelope",
        {},
        None,
    )


class Client:
    def __init__(self, base_url: str, *, transport: httpx.BaseTransport | None = None) -> None:
        self.base_url = check_base_url(base_url)  # before any transport exists
        self._http = httpx.Client(
            base_url=self.base_url,
            transport=transport,
            follow_redirects=False,
            trust_env=False,  # no proxy or netrc credentials from the environment
            headers={"User-Agent": f"saveclock-cli/{__version__}"},
            timeout=httpx.Timeout(30.0, read=120.0, write=300.0),
        )

    def close(self) -> None:
        self._http.close()

    @staticmethod
    def _path(op: str, params: dict[str, str] | None) -> tuple[str, str]:
        method, template = ENDPOINTS[op]
        quoted = {k: urllib.parse.quote(v, safe="") for k, v in (params or {}).items()}
        return method, template.format(**quoted)

    def _check(self, resp: httpx.Response) -> None:
        if HTTPStatus.MULTIPLE_CHOICES <= resp.status_code < HTTPStatus.BAD_REQUEST:
            raise Refused(
                "the API answered with a redirect; the CLI follows none",
                code="redirect",
                exit_code=EXIT_NETWORK,
            )
        if resp.status_code >= HTTPStatus.BAD_REQUEST:
            resp.read()
            raise _error_from(resp)

    def call(
        self,
        op: str,
        *,
        params: dict[str, str] | None = None,
        query: dict[str, str] | None = None,
        json: Any = None,  # noqa: ANN401
        content: Iterator[bytes] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        method, path = self._path(op, params)
        try:
            resp = self._http.request(
                method, path, params=query, json=json, content=content, headers=headers
            )
        except httpx.HTTPError as exc:
            raise NetworkError(
                f"{type(exc).__name__}: could not reach the API at {self.base_url}"
            ) from exc
        self._check(resp)
        return resp

    @contextmanager
    def stream(
        self, op: str, *, params: dict[str, str] | None = None, query: dict[str, str] | None = None
    ) -> Iterator[httpx.Response]:
        method, path = self._path(op, params)
        try:
            with self._http.stream(method, path, params=query) as resp:
                self._check(resp)
                yield resp
        except httpx.HTTPError as exc:
            raise NetworkError(f"{type(exc).__name__}: the connection to the API failed") from exc

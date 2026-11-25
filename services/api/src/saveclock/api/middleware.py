"""Pure ASGI middlewares (no BaseHTTPMiddleware: it buffers streaming bodies).

Order, outermost first: request id, access guard, security headers.
"""

import re

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from saveclock.api.error_handlers import SECURITY_HEADERS, error_response
from saveclock.config import Settings
from saveclock.errors import Forbidden, ForbiddenReason
from saveclock.ids import new_request_id

REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        inbound = Headers(scope=scope).get("x-request-id", "")
        request_id = inbound if REQUEST_ID_RE.match(inbound) else new_request_id()
        # Not cleared afterwards: the error handlers that run outside this middleware read it,
        # and every request has its own task context.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["x-request-id"] = request_id
            await send(message)

        await self.app(scope, receive, send_with_id)


STATE_CHANGING = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def hostname(host_header: str) -> str:
    """`localhost:3000` -> `localhost`; `[::1]:8000` -> `::1`; lowercase, no trailing dot."""
    host = host_header.strip().lower()
    if host.startswith("["):
        host = host[1:].split("]", 1)[0]
    elif host.count(":") == 1:
        host = host.split(":", 1)[0]
    return host.rstrip(".")


class AccessGuardMiddleware:
    """Host allowlist (DNS rebinding), Sec-Fetch-Site and Origin checks (SEC-165..167).

    Applies to every http path, health included, and answers without calling the app.
    """

    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        self.app = app
        self.allowed_hosts = {h.lower().rstrip(".") for h in settings.allowed_hosts}
        self.app_origin = settings.app_origin.lower().rstrip("/")

    def _violation(self, scope: Scope) -> ForbiddenReason | None:
        headers = Headers(scope=scope)
        if hostname(headers.get("host", "")) not in self.allowed_hosts:
            return ForbiddenReason.HOST_NOT_ALLOWED
        if headers.get("sec-fetch-site") == "cross-site":
            return ForbiddenReason.CROSS_SITE
        origin = headers.get("origin")
        # No Origin at all is accepted (CLI, curl, tests; OQ-27). "null" is a present, foreign one.
        if (
            scope["method"] in STATE_CHANGING
            and origin is not None
            and origin.lower().rstrip("/") != self.app_origin
        ):
            return ForbiddenReason.ORIGIN_MISMATCH
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        reason = self._violation(scope)
        if reason is None:
            await self.app(scope, receive, send)
            return
        err = Forbidden(reason)
        response = error_response(err.code, err.message, err.details, err.status)
        await response(scope, receive, send)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS.items():
                    headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)

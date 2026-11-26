"""One envelope for every non-2xx (ARCH §7). Never a trace, never an echoed input value."""

from http import HTTPStatus
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from saveclock.errors import HTTP_STATUS, AppError, ErrorCode

SECURITY_HEADERS: dict[str, str] = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
    "cache-control": "private, no-store",
}

log = structlog.get_logger()


def current_request_id() -> str:
    return str(structlog.contextvars.get_contextvars().get("request_id", ""))


def error_response(
    code: ErrorCode,
    message: str,
    details: dict[str, Any] | None = None,
    status: int | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Built here (not by middleware) so errors raised outside the router keep the same shape.

    Carries the request id and security headers itself: ServerErrorMiddleware and the access
    guard answer without passing back through the inner middlewares.
    """
    request_id = current_request_id()
    body = {
        "error": {
            "code": code.value,
            "message": message,
            "details": details,
            "request_id": request_id,
            "doc_url": None,
        }
    }
    out = {**SECURITY_HEADERS, **(headers or {})}
    if request_id:
        out["x-request-id"] = request_id
    return JSONResponse(body, status_code=status or HTTP_STATUS[code] or 500, headers=out)


async def _app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)  # noqa: S101
    return error_response(exc.code, exc.message, exc.details, exc.status, exc.headers)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    fields = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return error_response(ErrorCode.VALIDATION_ERROR, "invalid request", {"fields": fields})


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    found = exc.status_code == HTTPStatus.NOT_FOUND
    code = ErrorCode.NOT_FOUND if found else ErrorCode.BAD_REQUEST
    message = "not found" if found else "request not allowed"
    return error_response(code, message, None, exc.status_code)


async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
    log.error("request.failed", exc_type=type(exc).__name__, exc_info=exc)
    return error_response(ErrorCode.INTERNAL_ERROR, "internal error")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unhandled)

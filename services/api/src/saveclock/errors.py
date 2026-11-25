"""Error catalogue (ARCH §7). Shared kernel: importable by every layer.

`ErrorCode` is the one owner of the codes; the OpenAPI enum and the TS type derive from it.
"""

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "validation_error"
    BAD_REQUEST = "bad_request"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    PLAN_VERSION_CONFLICT = "plan_version_conflict"
    LOCK_CONFLICT = "lock_conflict"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    UNSUPPORTED_MEDIA = "unsupported_media"
    FILE_REJECTED = "file_rejected"
    INSUFFICIENT_STORAGE = "insufficient_storage"
    PIXABAY_NOT_CONFIGURED = "pixabay_not_configured"
    STOCK_UNAVAILABLE = "stock_unavailable"
    CLIP_UNAVAILABLE = "clip_unavailable"
    VERIFICATION_FAILED = "verification_failed"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    INTERNAL_ERROR = "internal_error"


# None = a job error code that never appears as an HTTP status.
HTTP_STATUS: dict[ErrorCode, int | None] = {
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.BAD_REQUEST: 400,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.PLAN_VERSION_CONFLICT: 409,
    ErrorCode.LOCK_CONFLICT: 409,
    ErrorCode.PAYLOAD_TOO_LARGE: 413,
    ErrorCode.UNSUPPORTED_MEDIA: 415,
    ErrorCode.FILE_REJECTED: 422,
    ErrorCode.INSUFFICIENT_STORAGE: 507,
    ErrorCode.PIXABAY_NOT_CONFIGURED: 409,
    ErrorCode.STOCK_UNAVAILABLE: None,
    ErrorCode.CLIP_UNAVAILABLE: None,
    ErrorCode.VERIFICATION_FAILED: None,
    ErrorCode.UPSTREAM_UNAVAILABLE: 503,
    ErrorCode.INTERNAL_ERROR: 500,
}


class ForbiddenReason(StrEnum):
    HOST_NOT_ALLOWED = "host_not_allowed"
    ORIGIN_MISMATCH = "origin_mismatch"
    CROSS_SITE = "cross_site"


class AppError(Exception):
    code: ErrorCode = ErrorCode.INTERNAL_ERROR

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    @property
    def status(self) -> int:
        return HTTP_STATUS[self.code] or 500


class NotFound(AppError):
    code = ErrorCode.NOT_FOUND

    def __init__(self, message: str = "not found") -> None:
        super().__init__(message)


class BadRequest(AppError):
    code = ErrorCode.BAD_REQUEST


class Forbidden(AppError):
    code = ErrorCode.FORBIDDEN

    def __init__(self, reason: ForbiddenReason, message: str = "forbidden") -> None:
        super().__init__(message, {"reason": reason.value})


class UpstreamUnavailable(AppError):
    code = ErrorCode.UPSTREAM_UNAVAILABLE


class InsufficientStorage(AppError):
    code = ErrorCode.INSUFFICIENT_STORAGE


class PayloadTooLarge(AppError):
    code = ErrorCode.PAYLOAD_TOO_LARGE


class InternalError(AppError):
    code = ErrorCode.INTERNAL_ERROR

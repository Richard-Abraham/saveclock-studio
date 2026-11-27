"""Error catalogue (ARCH §7). Shared kernel: importable by every layer.

`ErrorCode` is the one owner of the codes; the OpenAPI enum and the TS type derive from it.
"""

from enum import StrEnum
from typing import Any

from saveclock.domain.audio_rules import FileRejectReason


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


class UnsupportedMediaReason(StrEnum):
    UNSNIFFABLE = "unsniffable"
    EXTENSION_MISMATCH = "extension_mismatch"
    MIME_MISMATCH = "mime_mismatch"


class BadRequestReason(StrEnum):
    CONTENT_LENGTH_REQUIRED = "content_length_required"
    BAD_FILENAME = "bad_filename"


class ConflictReason(StrEnum):
    NOT_READY = "not_ready"
    WRONG_STATE = "wrong_state"
    UPLOAD_IN_PROGRESS = "upload_in_progress"
    RETRY_LIMIT = "retry_limit"
    JOB_ACTIVE = "job_active"  # uq_jobs_active: another draft, replan or render is running
    NO_PLAN_YET = "no_plan_yet"
    TOO_MANY_STREAMS = "too_many_streams"
    RENDER_ACTIVE = "render_active"  # a replan-fetch while a render runs (P6-11)


# ARCH §7: which codes a client (or the job runner) may retry; derived from the code, no column.
RETRYABLE = frozenset(
    {
        ErrorCode.CONFLICT,
        ErrorCode.INSUFFICIENT_STORAGE,
        ErrorCode.STOCK_UNAVAILABLE,
        ErrorCode.VERIFICATION_FAILED,
        ErrorCode.UPSTREAM_UNAVAILABLE,
        ErrorCode.INTERNAL_ERROR,
    }
)


class AppError(Exception):
    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    status_override: int | None = None  # for the rare status the catalogue does not map (416)

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        self.headers = headers or {}

    @property
    def status(self) -> int:
        return self.status_override or HTTP_STATUS[self.code] or 500


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


class Conflict(AppError):
    code = ErrorCode.CONFLICT

    def __init__(self, reason: ConflictReason, message: str = "conflict") -> None:
        super().__init__(message, {"reason": reason.value})


class UnsupportedMedia(AppError):
    code = ErrorCode.UNSUPPORTED_MEDIA

    def __init__(self, reason: UnsupportedMediaReason, message: str = "unsupported media") -> None:
        super().__init__(message, {"reason": reason.value})


class FileRejected(AppError):
    code = ErrorCode.FILE_REJECTED

    def __init__(self, reason: FileRejectReason, message: str = "file rejected") -> None:
        super().__init__(message, {"reason": reason.value})


class PlanVersionConflict(AppError):
    """A stale `base_version`: the client refetches (ARCH §7)."""

    code = ErrorCode.PLAN_VERSION_CONFLICT

    def __init__(self, current_version: int) -> None:
        super().__init__("plan version conflict", {"current_version": current_version})


class LockConflictError(AppError):
    """A replan cannot honour a locked clip (ARCH §5 invariant 7)."""

    code = ErrorCode.LOCK_CONFLICT

    def __init__(self, reason: str) -> None:
        super().__init__("a locked clip cannot stay", {"reason": reason})


class ValidationFailed(AppError):
    """A well-formed request that the domain refuses (422 `validation_error` with a reason)."""

    code = ErrorCode.VALIDATION_ERROR

    def __init__(self, reason: str, rule: str | None = None) -> None:
        details = {"reason": reason, **({"rule": rule} if rule else {})}
        super().__init__("request refused", details)


class UpstreamUnavailable(AppError):
    code = ErrorCode.UPSTREAM_UNAVAILABLE


class InsufficientStorage(AppError):
    code = ErrorCode.INSUFFICIENT_STORAGE


class PayloadTooLarge(AppError):
    code = ErrorCode.PAYLOAD_TOO_LARGE


class InternalError(AppError):
    code = ErrorCode.INTERNAL_ERROR


class RangeNotSatisfiable(BadRequest):
    status_override = 416

    def __init__(self, size: int) -> None:
        super().__init__(
            "range not satisfiable", {"size": size}, {"content-range": f"bytes */{size}"}
        )


class PixabayNotConfigured(AppError):
    """`PUT /settings` enabled Pixabay while no key is configured on the worker."""

    code = ErrorCode.PIXABAY_NOT_CONFIGURED

    def __init__(self) -> None:
        super().__init__("no Pixabay key is configured")


class StockUnavailable(AppError):
    """The stock provider could not answer (job error `stock_unavailable`, retryable)."""

    code = ErrorCode.STOCK_UNAVAILABLE


class ClipUnavailable(AppError):
    """A clip could not be fetched or prepared (job error `clip_unavailable`)."""

    code = ErrorCode.CLIP_UNAVAILABLE

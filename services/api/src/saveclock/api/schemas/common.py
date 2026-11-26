from typing import Any

from pydantic import BaseModel, ConfigDict

from saveclock.errors import ErrorCode, ForbiddenReason


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ErrorCode
    message: str
    details: dict[str, Any] | None = None
    request_id: str
    doc_url: str | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    error: ErrorBody


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    403: {
        "model": ErrorResponse,
        "description": "forbidden; details.reason is one of "
        + ", ".join(r.value for r in ForbiddenReason),
    },
    404: {"model": ErrorResponse, "description": "not found"},
    422: {"model": ErrorResponse, "description": "validation_error (details.fields)"},
    500: {"model": ErrorResponse, "description": "internal_error"},
}

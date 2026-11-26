from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.api.deps import current_user, get_deps, get_session, get_settings
from saveclock.api.schemas.common import (
    BAD_REQUEST_RESPONSE,
    CONFLICT_RESPONSE,
    ERROR_RESPONSES,
    UPLOAD_RESPONSES,
)
from saveclock.api.schemas.projects import UploadAccepted
from saveclock.config import Settings
from saveclock.deps import Deps
from saveclock.services.identity import CurrentUser
from saveclock.services.ingest import receive_upload

router = APIRouter(prefix="/projects", tags=["upload"], responses=ERROR_RESPONSES)

RAW_BODY = {
    "requestBody": {
        "required": True,
        "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
    }
}


@router.post(
    "/{project_id}/song",
    operation_id="upload_song",
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra=RAW_BODY,
    responses={**BAD_REQUEST_RESPONSE, **CONFLICT_RESPONSE, **UPLOAD_RESPONSES},
)
async def upload_song(  # noqa: PLR0917 - FastAPI dependencies and headers
    project_id: UUID,
    request: Request,
    user: Annotated[CurrentUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    deps: Annotated[Deps, Depends(get_deps)],
    settings: Annotated[Settings, Depends(get_settings)],
    content_length: Annotated[str | None, Header()] = None,
    content_type: Annotated[str | None, Header()] = None,
    x_filename: Annotated[str | None, Header()] = None,
) -> UploadAccepted:
    """One streamed upload: raw body, `Content-Length` required, `X-Filename` percent-encoded."""
    result = await receive_upload(
        session,
        user_id=user.id,
        project_id=project_id,
        content_length=content_length,
        content_type=content_type,
        x_filename=x_filename,
        body=request.stream(),
        blobs=deps.blobs,
        enqueuer=deps.enqueuer,
        settings=settings,
        publisher=deps.publisher,
    )
    return UploadAccepted(job_id=result.job_id, ui_status=result.ui_status)

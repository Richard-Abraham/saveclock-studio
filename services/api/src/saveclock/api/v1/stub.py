"""The named stub job routes (not part of the 27). Registered only when APP_ENV is local or ci."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.api.deps import current_user, get_deps, get_session
from saveclock.api.schemas.common import ERROR_RESPONSES
from saveclock.api.schemas.stub import StubChain, StubHop, StubJobIn, StubJobOut
from saveclock.deps import Deps
from saveclock.errors import InternalError
from saveclock.services.files import serve
from saveclock.services.identity import CurrentUser
from saveclock.services.stub import create_stub_job, download_key, get_chain

router = APIRouter(prefix="/_stub", tags=["stub"], responses=ERROR_RESPONSES)


@router.post("/jobs", operation_id="stub_create_job", status_code=202)
async def create(
    body: StubJobIn,
    user: Annotated[CurrentUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    deps: Annotated[Deps, Depends(get_deps)],
) -> StubJobOut:
    if deps.enqueue_stub is None:
        raise InternalError("stub jobs are not enabled")
    job_id, project_id = await create_stub_job(session, user.id, body.sleep_s, deps.enqueue_stub)
    return StubJobOut(job_id=job_id, project_id=project_id)


@router.get("/jobs/{job_id}", operation_id="stub_get_job")
async def read(
    job_id: UUID,
    user: Annotated[CurrentUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StubChain:
    chain = await get_chain(session, user.id, job_id)
    return StubChain(
        job_id=chain.job_id,
        project_id=chain.project_id,
        hops=[StubHop(**vars(h)) for h in chain.hops],
    )


@router.get("/jobs/{job_id}/download", operation_id="stub_download")
async def download(
    job_id: UUID,
    user: Annotated[CurrentUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    deps: Annotated[Deps, Depends(get_deps)],
    range_: Annotated[str | None, Header(alias="range")] = None,
) -> StreamingResponse:
    key = await download_key(session, user.id, job_id)
    out = serve(deps.blobs, key, range_)
    return StreamingResponse(out.body, status_code=out.status, headers=out.headers)

"""The named stub job routes (not part of the 27). Registered only when APP_ENV is local or ci."""

import asyncio
import hashlib
import json
import time
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.api.deps import current_user, get_deps, get_session
from saveclock.api.schemas.common import ERROR_RESPONSES
from saveclock.api.schemas.stub import StubChain, StubHop, StubJobIn, StubJobOut, UploadSinkOut
from saveclock.deps import Deps
from saveclock.errors import BadRequest
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
    assert deps.enqueue_stub is not None  # noqa: S101 - the router is only mounted when it is set
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


# shortcut: the two measurement routes below exist only for OQ-26 (plan 002 Step 7) and are
# kept out of the OpenAPI schema; delete in Phase 2 with measure_rewrite.
@router.get("/sse", operation_id="stub_sse", include_in_schema=False)
async def sse(
    user: Annotated[CurrentUser, Depends(current_user)],
    events: Annotated[int, Query(ge=1, le=120)] = 30,
    interval_ms: Annotated[int, Query(ge=100, le=5000)] = 1000,
) -> StreamingResponse:
    del user  # owner-scoped: resolving the user is the access check

    async def stream() -> AsyncIterator[str]:
        for n in range(events):
            if n:
                await asyncio.sleep(interval_ms / 1000)
            yield f"data: {json.dumps({'i': n, 't': int(time.time() * 1000)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/upload-sink", operation_id="stub_upload_sink", include_in_schema=False)
async def upload_sink(
    request: Request, user: Annotated[CurrentUser, Depends(current_user)]
) -> UploadSinkOut:
    del user
    if "content-length" not in request.headers:
        raise BadRequest("Content-Length is required")
    start = time.monotonic()
    digest = hashlib.sha256()
    total = 0
    first_ms = 0
    first_at_ms = 0
    last_ms = 0
    async for chunk in request.stream():  # never stored, never accumulated
        if not chunk:
            continue
        now_ms = int((time.monotonic() - start) * 1000)
        if total == 0:
            first_ms = now_ms
            first_at_ms = int(time.time() * 1000)
        last_ms = now_ms
        total += len(chunk)
        digest.update(chunk)
    return UploadSinkOut(
        bytes=total,
        sha256=digest.hexdigest(),
        first_chunk_ms=first_ms,
        last_chunk_ms=last_ms,
        first_chunk_at_ms=first_at_ms,
    )

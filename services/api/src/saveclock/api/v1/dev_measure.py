"""The two OQ-26 measurement routes (plan 002 Step 7), kept when the Phase 1 demo job went.

Registered only when APP_ENV is local or ci (`main.py`) and kept out of the OpenAPI schema; the
scripts `measure_rewrite.py` and `web_http.py` and the CORS tests call them.
"""

import asyncio
import hashlib
import json
import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from saveclock.api.deps import current_user
from saveclock.api.schemas.common import ERROR_RESPONSES
from saveclock.errors import BadRequest
from saveclock.services.identity import CurrentUser

router = APIRouter(prefix="/_measure", tags=["dev"], responses=ERROR_RESPONSES)


class UploadSinkOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    bytes: int
    sha256: str
    first_chunk_ms: int
    last_chunk_ms: int
    first_chunk_at_ms: int


@router.get("/sse", operation_id="measure_sse", include_in_schema=False)
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


@router.post("/upload-sink", operation_id="measure_upload_sink", include_in_schema=False)
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

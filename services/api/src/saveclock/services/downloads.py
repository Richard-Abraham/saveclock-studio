"""Downloading a render's files (#21): owner-scoped, a fixed set of kinds, streamed with ranges."""

import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.adapters.blobstore.blob_keys import render_file_key
from saveclock.adapters.blobstore.port import BlobStore
from saveclock.domain.filenames import normalise
from saveclock.domain.render_job import RENDER_FILES, DownloadKind
from saveclock.errors import Conflict, ConflictReason, NotFound
from saveclock.models import ModeAState, RenderState
from saveclock.repositories.projects import ProjectRepository
from saveclock.repositories.renders import RenderRepository
from saveclock.services.files import Served, serve

MAX_SLUG = 60
_SLUG_BAD = re.compile(r"[\s\"'`<>:|?*]+")


def slug_of(title: str | None, render_id: UUID) -> str:
    """A download name stem from the project title (normalised, no separators or quotes);
    `saveclock-{id8}` when there is no usable title."""
    cleaned = _SLUG_BAD.sub("-", normalise(title)) if title and title.strip() else ""
    cleaned = cleaned.strip("-.")[:MAX_SLUG].strip("-.")
    return cleaned or f"saveclock-{str(render_id)[:8]}"


def download_name(title: str | None, render_id: UUID, kind: DownloadKind) -> str:
    ext = RENDER_FILES[kind.value].rpartition(".")[2]
    return f"{slug_of(title, render_id)}-{kind.value}.{ext}"


async def download(
    session: AsyncSession,
    blobs: BlobStore,
    user_id: UUID,
    render_id: UUID,
    kind: DownloadKind,
    *,
    range_header: str | None,
) -> Served:
    """404 for a render that is not the user's; 409 until the file exists (`with_song` needs Mode
    A). `kind` is the enum, so a free-form string never reaches a blob key."""
    render = await RenderRepository(session).get(user_id=user_id, render_id=render_id)
    if render is None:
        raise NotFound
    if kind is DownloadKind.WITH_SONG:
        if render.mode_a_state != ModeAState.READY.value:
            raise Conflict(ConflictReason.NOT_READY)
    elif render.state != RenderState.READY.value:
        raise Conflict(ConflictReason.NOT_READY)
    title = await RenderRepository(session).project_title(user_id=user_id, render=render)
    key = render_file_key(render_id, RENDER_FILES[kind.value])
    served = serve(blobs, key, range_header, download_name=download_name(title, render_id, kind))
    await ProjectRepository(session).touch(user_id=user_id, project_id=render.project_id)
    await session.commit()
    return served

"""Upload (API side) and audio validation (worker side): the first untrusted input (SEC-003..018).

`receive_upload` streams the body to `songs/{pid}/incoming.bin` under a running byte cap, with the
first 16 bytes sniffed before anything is stored. `validate_song` probes and decodes the file in an
audited FFmpeg child, rejects what is not a song, keeps the byte-identical original as
`songs/{pid}/source.<ext>` and writes `work/{pid}/canonical.flac` (decode-once).
"""

import asyncio
import hashlib
import queue
import threading
import time
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.adapters.blobstore.blob_keys import (
    canonical_key,
    song_incoming_key,
    song_source_key,
)
from saveclock.adapters.blobstore.port import BlobStore
from saveclock.adapters.events import EventPublisher
from saveclock.adapters.ffmpeg import (
    DecodeFailed,
    FfCanceled,
    ProbeFailed,
    canonicalize,
    probe_audio,
)
from saveclock.adapters.queue import Enqueuer
from saveclock.config import Settings
from saveclock.domain.audio_rules import FileRejectReason, check_audio, codec_label, first_audio
from saveclock.domain.filenames import display_title, ext_of, normalise
from saveclock.domain.media_sniff import (
    ALLOWED_EXT,
    HEAD_BYTES,
    MIME_TO_FMT,
    NotSniffable,
    sniff,
)
from saveclock.errors import (
    BadRequest,
    BadRequestReason,
    Conflict,
    ConflictReason,
    NotFound,
    PayloadTooLarge,
    UnsupportedMedia,
    UnsupportedMediaReason,
)
from saveclock.ids import new_id
from saveclock.models import JobQueue, JobStage, ProjectStatus
from saveclock.repositories.jobs import JobRepository
from saveclock.repositories.projects import ProjectRepository
from saveclock.repositories.songs import SongRepository
from saveclock.services import project_state
from saveclock.services.context import WorkerContext, cancel_probe, end_unwanted, hand_off
from saveclock.services.events import ProgressEmitter, ProgressTicker
from saveclock.services.projects import ui_status
from saveclock.services.scratch import scratch_dir

log = structlog.get_logger()

VALIDATE_EXPECTED_S = 10.0  # a typical song; the ticker only needs the right order of magnitude

MB = 1024 * 1024
QUEUE_DEPTH = 8
MAX_CANONICAL_BYTES = 1024 * MB
UPLOAD_FROM = (
    ProjectStatus.CREATED.value,
    ProjectStatus.REJECTED.value,
    ProjectStatus.CANCELED.value,
)
OCTET = "application/octet-stream"
STALE_UPLOAD_S = 600  # an `uploading` project untouched this long was abandoned (API killed)


# --- upload (API side) ------------------------------------------------------------------------


@dataclass(frozen=True)
class Upload:
    job_id: UUID
    ui_status: str


class _Abort(Exception):  # internal signal to the writer thread
    pass


def declared_length(header: str | None, cap: int) -> int:
    try:
        length = int(header) if header is not None else -1
    except ValueError:
        length = -1
    if length < 0:
        raise BadRequest(
            "Content-Length is required", {"reason": BadRequestReason.CONTENT_LENGTH_REQUIRED.value}
        )
    if length > cap:
        raise PayloadTooLarge("upload exceeds the size limit", {"max_bytes": cap})
    return length


def decode_filename(header: str | None) -> str:
    try:
        return normalise(unquote(header or "", errors="strict"))
    except UnicodeDecodeError:
        raise BadRequest(
            "X-Filename is not valid UTF-8", {"reason": BadRequestReason.BAD_FILENAME.value}
        ) from None


async def _head_and_rest(
    body: AsyncIterator[bytes],
) -> tuple[bytes, list[bytes], AsyncIterator[bytes]]:
    """Buffer chunks until HEAD_BYTES are in hand (or the body ends)."""
    seen: list[bytes] = []
    size = 0
    while size < HEAD_BYTES:
        try:
            chunk = await anext(body)
        except StopAsyncIteration:
            break
        seen.append(chunk)
        size += len(chunk)
    return b"".join(seen)[:HEAD_BYTES], seen, body


async def _store(
    blobs: BlobStore,
    key: str,
    buffered: list[bytes],
    rest: AsyncIterator[bytes],
    *,
    cap: int,
    declared: int,
) -> int:
    """Bridge the async request stream to the synchronous `BlobStore.put` through a bounded queue.

    The writer enforces `cap`; the stream must end at exactly `declared` bytes.
    """
    q: queue.Queue[bytes | None] = queue.Queue(maxsize=QUEUE_DEPTH)
    stop = threading.Event()

    def chunks() -> Iterator[bytes]:
        while True:
            try:
                item = q.get(timeout=0.1)
            except queue.Empty:
                if stop.is_set():
                    raise _Abort from None
                continue
            if item is None:
                return
            yield item

    writer = asyncio.create_task(asyncio.to_thread(blobs.put, key, chunks(), max_bytes=cap))

    async def offer(item: bytes | None) -> None:
        while True:
            if writer.done():
                await writer  # raises the writer's error (PayloadTooLarge, disk errors)
                return
            try:
                q.put_nowait(item)
                return
            except queue.Full:
                await asyncio.sleep(0.005)

    try:
        for chunk in buffered:
            await offer(chunk)
        async for chunk in rest:
            await offer(chunk)
        await offer(None)
        written = await writer
    except BaseException:
        stop.set()
        await asyncio.gather(writer, return_exceptions=True)
        raise
    if written != declared:
        blobs.delete(key)
        raise BadRequest(
            "body is shorter than Content-Length",
            {"reason": BadRequestReason.CONTENT_LENGTH_REQUIRED.value},
        )
    return written


async def receive_upload(
    session: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    content_length: str | None,
    content_type: str | None,
    x_filename: str | None,
    body: AsyncIterator[bytes],
    blobs: BlobStore,
    enqueuer: Enqueuer,
    settings: Settings,
    publisher: EventPublisher | None = None,
) -> Upload:
    projects = ProjectRepository(session)
    if await projects.get(user_id=user_id, project_id=project_id) is None:
        raise NotFound
    max_bytes = settings.max_upload_mb * MB
    declared = declared_length(content_length, max_bytes)  # 413 before a byte is read
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime != OCTET and not mime.startswith("audio/"):
        raise UnsupportedMedia(UnsupportedMediaReason.MIME_MISMATCH)
    filename = decode_filename(x_filename)
    blobs.ensure_free_space(declared)  # 507
    await projects.release_stale_upload(
        user_id=user_id, project_id=project_id, older_than_s=STALE_UPLOAD_S
    )
    if not await project_state.transition(  # commits: the other upload's 409 must see it now
        session,
        publisher,
        user_id=user_id,
        project_id=project_id,
        from_=UPLOAD_FROM,
        to=ProjectStatus.UPLOADING.value,
    ):
        raise Conflict(ConflictReason.UPLOAD_IN_PROGRESS)
    incoming = song_incoming_key(project_id)
    try:
        head, buffered, rest = await _head_and_rest(body)
        try:
            sniffed = sniff(head)
        except NotSniffable:
            raise UnsupportedMedia(UnsupportedMediaReason.UNSNIFFABLE) from None
        if ext_of(filename) not in ALLOWED_EXT[sniffed.fmt]:
            raise UnsupportedMedia(UnsupportedMediaReason.EXTENSION_MISMATCH)
        if mime != OCTET and MIME_TO_FMT.get(mime) != sniffed.fmt:
            raise UnsupportedMedia(UnsupportedMediaReason.MIME_MISMATCH)
        for key in blobs.list(f"songs/{project_id}"):  # a new song replaces the kept original
            if key.startswith(f"songs/{project_id}/source."):
                blobs.delete(key)
        size = await _store(
            blobs, incoming, buffered, rest, cap=min(declared, max_bytes), declared=declared
        )
        await SongRepository(session).create_or_replace(
            user_id=user_id,
            project_id=project_id,
            original_filename=filename,
            size_bytes=size,
            content_type=mime,
        )
        await projects.update_fields(
            user_id=user_id,
            project_id=project_id,
            values={"upload_completed_at": datetime.now(UTC)},
        )
        if not await project_state.transition(
            session,
            publisher,
            user_id=user_id,
            project_id=project_id,
            from_=ProjectStatus.UPLOADING.value,
            to=ProjectStatus.VALIDATING.value,
            commit=False,
        ):
            raise Conflict(ConflictReason.WRONG_STATE)
        job_id = new_id()
        await JobRepository(session).create(
            user_id=user_id,
            project_id=project_id,
            job_id=job_id,
            stage=JobStage.VALIDATE.value,
            queue=JobQueue.ANALYSIS.value,
        )
        await session.commit()  # the worker must see the rows before the message exists
    except BaseException:
        await session.rollback()
        session.info.pop(project_state.PENDING, None)
        blobs.delete(incoming)
        await project_state.transition(
            session,
            publisher,
            user_id=user_id,
            project_id=project_id,
            from_=ProjectStatus.UPLOADING.value,
            to=ProjectStatus.CREATED.value,
        )
        raise
    await project_state.announce_pending(session, publisher)
    await asyncio.to_thread(enqueuer.send, "validate_audio", str(job_id), str(user_id))
    return Upload(job_id, ui_status(ProjectStatus.VALIDATING.value).value)


# --- validation (worker side) -----------------------------------------------------------------


@dataclass(frozen=True)
class Rejected:
    reason: FileRejectReason


@dataclass(frozen=True)
class Validated:
    duration_s: Decimal
    codec: str
    sample_rate: int | None
    channels: int | None
    sha256: bytes
    ext: str
    timings: dict[str, int]


def _find_original(blobs: BlobStore, project_id: UUID) -> str | None:
    """The incoming file, or (after a crash past the rename) the kept `source.<ext>`."""
    incoming = song_incoming_key(project_id)
    if blobs.exists(incoming):
        return incoming
    prefix = f"songs/{project_id}/source."
    return next((k for k in blobs.list(f"songs/{project_id}") if k.startswith(prefix)), None)


def _sha256(blobs: BlobStore, key: str) -> bytes:
    h = hashlib.sha256()
    for chunk in blobs.open(key):
        h.update(chunk)
    return h.digest()


def _read_chunks(path: Path) -> Iterator[bytes]:
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            yield chunk


def _ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _validate_blocking(
    ctx: WorkerContext, project_id: UUID, scratch: Path, cancel: Callable[[], bool]
) -> Validated | Rejected:
    blobs, settings = ctx.blobs, ctx.settings
    key = _find_original(blobs, project_id)
    if key is None:
        return Rejected(FileRejectReason.CORRUPT)
    try:
        sniffed = sniff(b"".join(blobs.open(key, (0, HEAD_BYTES - 1))))  # the authority
    except NotSniffable:
        blobs.delete(key)
        return Rejected(FileRejectReason.CORRUPT)
    started = time.monotonic()
    try:
        probe = probe_audio(ctx.tools, blobs.local_path(key), sniffed.fmt)
    except ProbeFailed:
        blobs.delete(key)
        return Rejected(FileRejectReason.CORRUPT)
    probe_ms = _ms(started)
    verdict = check_audio(probe, min_s=settings.min_song_s, max_s=settings.max_song_s)
    audio = first_audio(probe)
    if verdict is not None or audio is None or probe.duration_s is None:
        blobs.delete(key)
        return Rejected(verdict or FileRejectReason.CORRUPT)
    digest = _sha256(blobs, key)
    started = time.monotonic()
    flac = scratch / "canonical.flac"
    try:
        canonicalize(ctx.tools, blobs.local_path(key), sniffed.fmt, flac, cancel=cancel)
    except DecodeFailed:
        blobs.delete(key)
        return Rejected(FileRejectReason.DECODE_FAILED)
    canonical_ms = _ms(started)
    blobs.put(canonical_key(project_id), _read_chunks(flac), max_bytes=MAX_CANONICAL_BYTES)
    if key == song_incoming_key(project_id):
        blobs.rename(key, song_source_key(project_id, sniffed.ext))
    return Validated(
        duration_s=Decimal(str(round(probe.duration_s, 3))),
        codec=codec_label(audio),
        sample_rate=audio.sample_rate,
        channels=audio.channels,
        sha256=digest,
        ext=sniffed.ext,
        timings={"probe_ms": probe_ms, "canonicalize_ms": canonical_ms},
    )


async def validate_song(ctx: WorkerContext, job_id: UUID, user_id: UUID) -> None:
    """Actor body. A permanent rejection is a normal return after the state is written."""
    started = time.monotonic()
    async with ctx.sessionmaker() as session:
        jobs, projects = JobRepository(session), ProjectRepository(session)
        job = await jobs.begin(user_id=user_id, job_id=job_id)
        if job is None or job.project_id is None:
            await jobs.reject_foreign(user_id=user_id, job_id=job_id)  # SEC-020
            await session.commit()
            return
        project_id = job.project_id
        project = await projects.get(user_id=user_id, project_id=project_id)
        await session.commit()
    status = project.status if project is not None else None
    if (
        status == ProjectStatus.ANALYZING.value
    ):  # redelivery after the transition: finish the hand-off
        await _hand_off_to_analysis(ctx, user_id, job_id, project_id, {"redelivered": True})
        return
    if status != ProjectStatus.VALIDATING.value:
        await end_unwanted(ctx, user_id, job_id)
        return
    cancel = cancel_probe(ctx, user_id, job_id)
    emitter = ProgressEmitter(ctx.publisher, project_id)
    try:
        with (
            scratch_dir(ctx.settings.scratch_root, job_id) as scratch,
            ProgressTicker(emitter, "checking_file", expected_s=VALIDATE_EXPECTED_S),
        ):
            outcome = await asyncio.to_thread(_validate_blocking, ctx, project_id, scratch, cancel)
    except FfCanceled:
        await end_unwanted(ctx, user_id, job_id)
        return
    await emitter.aemit("checking_file", 1.0, force=True)
    async with ctx.sessionmaker() as session:
        jobs, projects = JobRepository(session), ProjectRepository(session)
        if isinstance(outcome, Rejected):
            await project_state.transition(
                session,
                ctx.publisher,
                user_id=user_id,
                project_id=project_id,
                from_=ProjectStatus.VALIDATING.value,
                to=ProjectStatus.REJECTED.value,
                reason=outcome.reason.value,
                commit=False,
            )
            await jobs.fail(user_id=user_id, job_id=job_id, error_code="file_rejected")
            await session.commit()
            await project_state.announce_pending(session, ctx.publisher)
            log.info("validate.rejected", reason=outcome.reason.value)
            return
        songs = SongRepository(session)
        song = await songs.get_by_project(user_id=user_id, project_id=project_id)
        await songs.set_probe(
            user_id=user_id,
            project_id=project_id,
            duration_s=outcome.duration_s,
            codec=outcome.codec,
            sample_rate=outcome.sample_rate,
            channels=outcome.channels,
            sha256=outcome.sha256,
            source_ext=outcome.ext,
        )
        if song is not None:
            await projects.set_title_if_empty(
                user_id=user_id,
                project_id=project_id,
                title=display_title(song.original_filename),
            )
        moved = await project_state.transition(
            session,
            ctx.publisher,
            user_id=user_id,
            project_id=project_id,
            from_=ProjectStatus.VALIDATING.value,
            to=ProjectStatus.ANALYZING.value,
            commit=False,
        )
        await session.commit()
        await project_state.announce_pending(session, ctx.publisher)
        canceled = not moved and ProjectStatus.CANCELED.value == await _status(
            projects, user_id, project_id
        )
    if canceled:
        await end_unwanted(ctx, user_id, job_id)
        return
    await _hand_off_to_analysis(
        ctx, user_id, job_id, project_id, {**outcome.timings, "total_ms": _ms(started)}
    )


async def _status(projects: ProjectRepository, user_id: UUID, project_id: UUID) -> str | None:
    project = await projects.get(user_id=user_id, project_id=project_id)
    return project.status if project is not None else None


async def _hand_off_to_analysis(
    ctx: WorkerContext, user_id: UUID, job_id: UUID, project_id: UUID, timings: dict[str, Any]
) -> None:
    await hand_off(
        ctx,
        user_id,
        job_id,
        project_id=project_id,
        next_stage=JobStage.ANALYZE,
        next_queue=JobQueue.ANALYSIS,
        actor="analyze_song",
        timings=timings,
    )

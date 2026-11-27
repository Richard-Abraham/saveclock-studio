"""Top-K mezzanines (T-2.8, T-2.22): only the best ~1.3x cuts clips are turned into frame-exact
1080x1920 30 fps files. Ranking happens first, on cheap low-resolution frames (P5-9).

One encode at a time per FFmpeg child (a semaphore of 2), each under its own heavy slot, so a slot
is never held longer than one encode and its checks (`NORMALIZE_HOLD_S`).
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

import structlog

from saveclock.adapters.blobstore.blob_keys import mezz_key, raw_key
from saveclock.adapters.ffmpeg import FfCanceled, FfError, FfTimeout, build_mezz, probe_video
from saveclock.adapters.heavy_lock import HeavyLockTimeout
from saveclock.config import FOOTAGE_WAIT_S
from saveclock.domain.framemath import FPS
from saveclock.domain.ranking import RankedClip, top_k_count
from saveclock.domain.stock_rules import RejectReason
from saveclock.domain.video_checks import video_checks
from saveclock.domain.windows import Window
from saveclock.errors import ClipUnavailable
from saveclock.ids import new_id
from saveclock.models import ClipStatus
from saveclock.repositories.candidates import CandidateRepository
from saveclock.services.analysis import JobCanceled
from saveclock.services.footage import FootageDeps, mark_candidate
from saveclock.services.scratch import scratch_dir

log = structlog.get_logger()

ENCODE_CONCURRENCY = 2
FRAME_TOLERANCE = 1  # a mezzanine may differ from its window by one frame (the probed count wins)
CHUNK = 1 << 20
MAX_MEZZ_BYTES = 1 << 30


@dataclass(frozen=True)
class NormalizedClip:
    provider: str
    provider_id: str
    query: str
    score: float
    mezz_frames: int  # the probed frame count: the truth for planner invariant 3


def _encode_and_check(
    deps: FootageDeps, project_id: UUID, clip: RankedClip, wait_s: float = FOOTAGE_WAIT_S
) -> int | RejectReason:
    """Encode the window, probe the result, and store it. The probed frame count, or why not.
    Waits up to `wait_s` for a heavy slot."""
    ctx = deps.ctx
    src = ctx.blobs.local_path(raw_key(project_id, clip.provider, clip.provider_id))
    with deps.heavy.hold(wait_s), scratch_dir(ctx.settings.scratch_root, new_id()) as tmp:
        out = tmp / "mezz.mp4"
        try:
            build_mezz(ctx.tools, src, clip.window, out, cancel=deps.cancel)
            probe = probe_video(ctx.tools, out)
        except (FfCanceled, FfTimeout):
            raise
        except FfError:
            return RejectReason.FFPROBE_FAILED
        checks = video_checks(probe, clip.window.frames, tolerance=FRAME_TOLERANCE)
        if not all(c.ok for c in checks):
            return RejectReason.FFPROBE_FAILED
        frames = int(
            next(s for s in probe["streams"] if s["codec_type"] == "video")["nb_read_frames"]
        )
        with out.open("rb") as f:
            ctx.blobs.put(
                mezz_key(project_id, clip.provider, clip.provider_id),
                iter(lambda: f.read(CHUNK), b""),
                max_bytes=MAX_MEZZ_BYTES,
            )
    return frames


async def _normalize(
    deps: FootageDeps,
    user_id: UUID,
    project_id: UUID,
    clip: RankedClip,
    *,
    wait_s: float = FOOTAGE_WAIT_S,
    raise_busy: bool = False,
) -> NormalizedClip | None:
    async with deps.ctx.sessionmaker() as session:
        row = await CandidateRepository(session).get_by_provider_id(
            user_id=user_id,
            project_id=project_id,
            provider=clip.provider,
            provider_id=clip.provider_id,
        )
    if (
        row is not None
        and row.status == ClipStatus.NORMALIZED.value
        and row.mezz_frames
        and deps.ctx.blobs.exists(mezz_key(project_id, clip.provider, clip.provider_id))
    ):  # a redelivered job: the stored result is the answer
        return NormalizedClip(
            clip.provider, clip.provider_id, clip.query, clip.score, row.mezz_frames
        )
    try:
        outcome = await asyncio.to_thread(_encode_and_check, deps, project_id, clip, wait_s)
    except FfCanceled as exc:
        raise JobCanceled from exc
    except HeavyLockTimeout:
        if raise_busy:  # the caller has its own budget and decides what a busy slot means
            raise
        return None  # transient: stays `ranked`, the next clip takes its place
    except FfTimeout:
        return None  # transient: stays `ranked`, the next clip takes its place
    if isinstance(outcome, RejectReason):
        await mark_candidate(
            deps,
            user_id,
            project_id,
            clip,
            status=ClipStatus.REJECTED_QUALITY.value,
            reject_reason=outcome.value,
        )
        return None
    await mark_candidate(
        deps,
        user_id,
        project_id,
        clip,
        status=ClipStatus.NORMALIZED.value,
        mezz_frames=outcome,
    )
    return NormalizedClip(clip.provider, clip.provider_id, clip.query, clip.score, outcome)


async def normalize_topk(
    deps: FootageDeps,
    *,
    user_id: UUID,
    project_id: UUID,
    ranked: Sequence[RankedClip],
    cuts: int,
    factor: float | None = None,
) -> list[NormalizedClip]:
    """Normalize the best `K = ceil(factor x cuts)` clips, in rank order. A clip whose mezzanine
    fails its checks is rejected and the next ranked clip takes its place; the others stay
    `ranked` (they are normalized later, one by one, only if a swap needs them)."""
    k = top_k_count(cuts, factor if factor is not None else deps.ctx.settings.topk_factor)
    gate = asyncio.Semaphore(ENCODE_CONCURRENCY)
    queue = list(ranked)
    done: list[NormalizedClip] = []

    async def one(clip: RankedClip) -> NormalizedClip | None:
        async with gate:
            return await _normalize(deps, user_id, project_id, clip)

    while len(done) < k and queue:
        batch, queue = queue[: k - len(done)], queue[k - len(done) :]
        done += [r for r in await asyncio.gather(*(one(c) for c in batch)) if r is not None]
    order = [(c.provider, c.provider_id) for c in ranked]
    done.sort(key=lambda n: order.index((n.provider, n.provider_id)))
    log.info("footage.normalize", wanted=k, normalized=len(done), tried=len(ranked) - len(queue))
    return done


async def normalize_one(
    deps: FootageDeps,
    *,
    user_id: UUID,
    project_id: UUID,
    provider: str,
    provider_id: str,
    wait_s: float | None = None,
) -> NormalizedClip:
    """Lazy normalize of one ranked candidate (a swap): from the stored window and the raw file.
    `wait_s` caps the wait for a heavy slot and makes a busy slot raise `HeavyLockTimeout`
    (rehydration spends a budget); without it the wait is FOOTAGE_WAIT_S and busy means None."""
    async with deps.ctx.sessionmaker() as session:
        row = await CandidateRepository(session).get_by_provider_id(
            user_id=user_id, project_id=project_id, provider=provider, provider_id=provider_id
        )
    if row is None or row.window_start_s is None or not row.mezz_frames:
        msg = "candidate has no stored window"
        raise ClipUnavailable(msg)
    if not deps.ctx.blobs.exists(raw_key(project_id, provider, provider_id)):
        msg = "the source clip is gone"
        raise ClipUnavailable(msg)
    clip = RankedClip(
        provider,
        provider_id,
        row.query,
        float(row.score or 0.0),
        Window(float(Decimal(row.window_start_s)), row.mezz_frames / FPS),
    )
    normalized = await _normalize(
        deps,
        user_id,
        project_id,
        clip,
        wait_s=FOOTAGE_WAIT_S if wait_s is None else wait_s,
        raise_busy=wait_s is not None,
    )
    if normalized is None:
        msg = "the clip could not be normalized"
        raise ClipUnavailable(msg)
    return normalized

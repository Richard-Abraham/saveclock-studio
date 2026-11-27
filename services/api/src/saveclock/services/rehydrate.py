"""Rehydration (ARCH §4, §16): fetch and re-encode the clips of a plan whose intermediates were
swept, so an old project still renders.

It never ranks and never changes the plan: each missing mezzanine is rebuilt from the clip's
stored window (`clip_candidates`), and the rebuilt frame count must equal the stored one. A clip
that is gone at its provider ends the render with `clip_unavailable` and the project's flag lists
the plan version and the cut indexes, so the owner can replan.
"""

import asyncio
import time
from uuid import UUID

import structlog

from saveclock.adapters.blobstore.blob_keys import raw_key
from saveclock.adapters.heavy_lock import HeavyLockTimeout
from saveclock.config import FOOTAGE_WAIT_S
from saveclock.domain.edit_plan import EditPlan
from saveclock.domain.stock_rules import MAX_DOWNLOAD_BYTES
from saveclock.errors import ClipUnavailable, StockUnavailable
from saveclock.repositories.candidates import CandidateRepository
from saveclock.repositories.projects import ProjectRepository
from saveclock.services.events import ProgressEmitter
from saveclock.services.footage import FootageDeps
from saveclock.services.normalize import normalize_one

log = structlog.get_logger()
FLAG = "clip_unavailable"


def _out_of_time() -> StockUnavailable:
    return StockUnavailable("rehydration ran out of time", {"reason": "rehydrate_deadline"})


async def rehydrate_plan(
    deps: FootageDeps,
    plan: EditPlan,
    *,
    user_id: UUID,
    project_id: UUID,
    emitter: ProgressEmitter,
    deadline_s: float,
) -> int:
    """Rebuild every missing mezzanine of `plan`, in plan order; returns how many were rebuilt.

    Raises `ClipUnavailable` (a clip is gone at its provider, or its rebuilt length differs) and
    a retryable `StockUnavailable` when `deadline_s` is spent (a retry continues: existing files
    are skipped).

    shortcut: an `InsufficientStorage` during rehydration is retried and ends `internal_error`;
    upgrade to a dedicated code when the owner sees it.
    """
    ctx = deps.ctx
    started = time.monotonic()
    providers = {p.name: p for p in deps.providers}
    todo = [c for c in plan.cuts if not ctx.blobs.exists(c.clip.mezzanine_key)]
    if not todo:
        return 0
    gone: list[int] = []
    rebuilt = 0
    try:
        for n, cut in enumerate(todo):
            clip = cut.clip
            if ctx.blobs.exists(clip.mezzanine_key):  # the same clip served an earlier cut
                continue
            remaining = deadline_s - (time.monotonic() - started)
            if remaining <= 0:
                raise _out_of_time()
            await emitter.aemit("restoring_clips", n / len(todo), force=True)
            raw = raw_key(project_id, clip.provider, clip.provider_id)
            if not ctx.blobs.exists(raw):
                provider = providers.get(clip.provider)
                found = (
                    await asyncio.to_thread(provider.video_by_id, clip.provider_id)
                    if provider is not None
                    else None
                )
                if provider is None or found is None:
                    gone.append(cut.index)
                    continue
                await asyncio.to_thread(ctx.blobs.ensure_free_space, MAX_DOWNLOAD_BYTES)
                await asyncio.to_thread(
                    provider.download,
                    found,
                    ctx.blobs,
                    raw,
                    max_bytes=MAX_DOWNLOAD_BYTES,
                    cancel=deps.cancel,
                )
            async with ctx.sessionmaker() as session:
                row = await CandidateRepository(session).get_by_provider_id(
                    user_id=user_id,
                    project_id=project_id,
                    provider=clip.provider,
                    provider_id=clip.provider_id,
                )
            stored = row.mezz_frames if row is not None else None
            try:  # the slot wait spends what is left of the budget, never more than FOOTAGE_WAIT_S
                done = await normalize_one(
                    deps,
                    user_id=user_id,
                    project_id=project_id,
                    provider=clip.provider,
                    provider_id=clip.provider_id,
                    wait_s=min(FOOTAGE_WAIT_S, deadline_s - (time.monotonic() - started)),
                )
            except HeavyLockTimeout as exc:
                raise _out_of_time() from exc
            if done.mezz_frames != stored:
                msg = "the rebuilt clip differs from the planned one"
                raise ClipUnavailable(msg, {"cut": cut.index})
            rebuilt += 1
    finally:  # also when a clip fails: files written must be swept again later
        await _bookkeep(deps, plan, user_id, project_id, rebuilt=rebuilt, gone=gone)
    if gone:
        raise ClipUnavailable("a clip is gone at its provider", {"cuts": sorted(gone)})
    log.info("rehydrate.done", rebuilt=rebuilt)
    return rebuilt


async def _bookkeep(
    deps: FootageDeps,
    plan: EditPlan,
    user_id: UUID,
    project_id: UUID,
    *,
    rebuilt: int,
    gone: list[int],
) -> None:
    async with deps.ctx.sessionmaker() as session:
        projects = ProjectRepository(session)
        if rebuilt:
            # candidates go back to `selected` (normalize demotes them); P8-16: swept again later
            keys = {(c.clip.provider, c.clip.provider_id) for c in plan.cuts}
            await CandidateRepository(session).mark_selected(
                user_id=user_id, project_id=project_id, keys=keys
            )
            await projects.mark_intermediates_restored(user_id=user_id, project_id=project_id)
        project = await projects.get(user_id=user_id, project_id=project_id)
        flags = dict(project.flags) if project is not None else {}
        if gone:
            flags[FLAG] = {"version": plan.version, "cuts": sorted(gone)}
        elif FLAG in flags:
            del flags[FLAG]
        if project is not None and flags != dict(project.flags):
            await projects.update_fields(
                user_id=user_id, project_id=project_id, values={"flags": flags}
            )
        await session.commit()

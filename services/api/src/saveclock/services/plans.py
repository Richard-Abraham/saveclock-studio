"""Reading and editing the plan (endpoints #11 and #12) and the one place a plan is assembled from
what is stored (the draft job and a local replan both use `build`).

A replan-local edit is synchronous and never a job; a replan-fetch (`set_keywords`) is a job.
Every write is all-or-nothing: the plan is validated before a row changes.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.adapters.blobstore.blob_keys import mezz_key
from saveclock.adapters.events import EventPublisher
from saveclock.adapters.queue import Enqueuer
from saveclock.domain import edit_plan as ep
from saveclock.domain import energy
from saveclock.domain.clip_assign import LockConflict, LockedCut, NoUsableClips, PoolClip
from saveclock.domain.framemath import FPS
from saveclock.domain.grid import GridChoice, GridError, GridView, choice_from_plan, effective_grid
from saveclock.domain.keywords import clean_keywords
from saveclock.domain.plan_hash import content_hash, with_hash
from saveclock.domain.plan_ops import (
    AnyOp,
    LockClip,
    OpContext,
    PlanOpError,
    ReplanState,
    SetKeywords,
    apply_ops,
    refuse_keyword_extras,
)
from saveclock.domain.planner import (
    BuiltPlan,
    PlanError,
    PlanInputs,
    SectionIn,
    build_plan,
    fit_length,
    layout_cuts,
    snap_start,
)
from saveclock.domain.segment import select_segment
from saveclock.errors import (
    Conflict,
    ConflictReason,
    LockConflictError,
    NotFound,
    PlanVersionConflict,
    ValidationFailed,
)
from saveclock.ids import new_id
from saveclock.models import (
    Analysis,
    ClipCandidate,
    JobQueue,
    JobStage,
    Project,
    ProjectStatus,
    Song,
)
from saveclock.repositories.analyses import AnalysisRepository
from saveclock.repositories.candidates import CandidateRepository
from saveclock.repositories.jobs import JobRepository
from saveclock.repositories.plans import PlanRepository, PlanVersionExists
from saveclock.repositories.projects import ProjectRepository
from saveclock.repositories.songs import SongRepository
from saveclock.services import project_state

DEFAULT_DURATION_S = 30
PATCHABLE = (
    ProjectStatus.DRAFT_READY.value,
    ProjectStatus.READY.value,
    ProjectStatus.RENDERING.value,
)


# --- the stored facts a plan is built from -------------------------------------------------------


@dataclass(frozen=True)
class Basis:
    project: Project
    song: Song
    analysis: Analysis
    latest: Any  # the newest `edit_plans` row, or None
    pool: list[ClipCandidate]


async def load_basis(session: AsyncSession, user_id: UUID, project_id: UUID) -> Basis:
    project = await ProjectRepository(session).get(user_id=user_id, project_id=project_id)
    if project is None:
        raise NotFound
    song = await SongRepository(session).get_by_project(user_id=user_id, project_id=project_id)
    analysis = await AnalysisRepository(session).get_by_project(
        user_id=user_id, project_id=project_id
    )
    if song is None or analysis is None or song.sha256 is None:
        raise Conflict(ConflictReason.NOT_READY)
    return Basis(
        project,
        song,
        analysis,
        await PlanRepository(session).latest(user_id=user_id, project_id=project_id),
        await CandidateRepository(session).list_pool(user_id=user_id, project_id=project_id),
    )


def seed_of(project_id: UUID) -> int:
    return int.from_bytes(project_id.bytes[:4], "big")


def song_duration(basis: Basis) -> float:
    return float(basis.song.duration_s or 0)


def pool_clips(project_id: UUID, rows: Sequence[ClipCandidate]) -> list[PoolClip]:
    return [
        PoolClip(
            r.provider,
            r.provider_id,
            r.query,
            round(float(r.score or 0.0), 6),
            mezz_key(project_id, r.provider, r.provider_id),
            int(r.mezz_frames or 0),
            ep.Attribution(author=r.author, author_url=r.author_url, page_url=r.page_url),
        )
        for r in rows
    ]


def rotation_keywords(pool: Sequence[PoolClip], override: Sequence[str] | None) -> list[str]:
    """The preferred keyword order of the clip step: the owner's, else the pool's queries by their
    best score (one rule for the draft and a local replan, so a density change keeps the clips)."""
    if override:
        return list(override)
    best: dict[str, float] = {}
    for c in pool:
        best[c.query] = max(best.get(c.query, -1.0), c.score)
    return sorted(best, key=lambda q: (-best[q], q))


def sections_of(analysis: Analysis) -> list[SectionIn]:
    return [
        SectionIn(str(s["id"]), float(s["start_s"]), float(s["end_s"]), str(s["energy"]))
        for s in analysis.sections
    ]


def locked_cuts(plan: ep.EditPlan, locks: Sequence[tuple[int, bool]]) -> list[LockedCut]:
    """The cuts the owner locked, after the lock flips of this edit (cut indexes of `plan`)."""
    flags = {c.index: c.clip.locked for c in plan.cuts}
    for index, locked in locks:
        flags[index] = locked
    return [
        LockedCut(
            c.beat_ref.t_s,
            PoolClip(
                c.clip.provider,
                c.clip.provider_id,
                c.clip.keywords[0] if c.clip.keywords else "",
                c.clip.score,
                c.clip.mezzanine_key,
                c.clip.mezzanine_frames,
                c.clip.attribution,
            ),
            c.clip.in_frame,
        )
        for c in plan.cuts
        if flags[c.index]
    ]


def grid_for(basis: Basis, choice: GridChoice) -> GridView:
    bm = basis.analysis.beat_map
    energy_grid = bm.get("grid", {}).get("beats_s") if basis.analysis.fallback else None
    return effective_grid(
        list(bm["raw"]["beats_s"]),
        list(bm["raw"]["downbeats_s"]),
        choice=choice,
        fallback_grid=list(energy_grid) if energy_grid else None,
        duration_s=song_duration(basis),
        model_name=f"{basis.analysis.model}:{basis.analysis.model_version}",
    )


def initial_state(basis: Basis) -> ReplanState:
    """The replan inputs as the latest plan holds them, or the draft's defaults."""
    a, project = basis.analysis, basis.project
    if basis.latest is not None:
        plan = ep.EditPlan.model_validate(basis.latest.plan)
        choice = choice_from_plan(
            plan.beat_grid.source,
            plan.beat_grid.tempo_octave_adjust,
            a.tempo_octave_adjust,
            plan.beat_grid.tempo_bpm,
        )
        return ReplanState(
            choice, plan.segment.start_s, plan.total_frames // FPS, plan.options.density
        )
    mode = "energy" if a.fallback == "energy_grid" else "detected"
    requested = int(project.options.get("duration", DEFAULT_DURATION_S))
    return ReplanState(
        GridChoice(mode),  # type: ignore[arg-type]
        float(a.beat_map.get("segment", {}).get("start_s", 0.0)),
        fit_length(requested, song_duration(basis)),
        int(project.options.get("density", 0)),
    )


def segment_start(basis: Basis, grid: GridView, state: ReplanState) -> float:
    """The segment's first downbeat: the loudest window for `auto`, else the nearest to the ask."""
    duration = song_duration(basis)
    start = state.start_s
    if state.auto_start:
        downs = list(grid.downbeats_s)
        bars = energy.bar_energy(list(basis.analysis.energy_curve), downs)
        start = select_segment(bars, downs, duration, state.length_s).start_s
    return snap_start(grid, start, state.length_s, duration)


def estimate_cuts(basis: Basis, state: ReplanState) -> int:
    """How many cuts the plan will have, before any clip exists (it sizes the clip search)."""
    grid = grid_for(basis, state.grid)
    return len(
        layout_cuts(
            grid,
            sections_of(basis.analysis),
            segment_start(basis, grid, state),
            state.length_s * FPS,
            density=state.density,
        ).slots
    )


def build(
    basis: Basis,
    state: ReplanState,
    *,
    version: int,
    plan_id: UUID,
    llm_model: str | None,
    keyword_source: ep.KeywordSourceName,
    keywords_override: list[str] | None,
    prior: ep.EditPlan | None,
    created_by: ep.CreatedBy = "planner",
    pool: Sequence[PoolClip] | None = None,
) -> BuiltPlan:
    """The planner on the stored facts. Raises the domain errors the callers map."""
    project = basis.project
    grid = grid_for(basis, state.grid)
    duration = song_duration(basis)
    start = segment_start(basis, grid, state)
    clips = list(pool) if pool is not None else pool_clips(project.id, basis.pool)
    locked = locked_cuts(prior, state.locks) if prior is not None else []
    inp = PlanInputs(
        project_id=project.id,
        plan_id=plan_id,
        version=version,
        song_sha256_hex=bytes(basis.song.sha256 or b"").hex(),
        song_duration_s=duration,
        song_sample_rate=basis.song.sample_rate or 48000,
        grid=grid,
        confidence=basis.analysis.beat_confidence,
        sections=sections_of(basis.analysis),
        start_s=start,
        total_frames=state.length_s * FPS,
        density=state.density,
        style=str(project.options.get("style", "default")),
        keywords_override=keywords_override,
        rotation_keywords=rotation_keywords(clips, keywords_override),
        pool=clips,
        locked=locked,
        seed=seed_of(project.id),
        llm_model=llm_model,
        keyword_source=keyword_source,
        created_by=created_by,
    )
    return build_plan(inp)


# --- reading (#11) ------------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanView:
    plan: ep.EditPlan
    frozen: bool


@dataclass(frozen=True)
class PlanSummary:
    version: int
    frozen: bool
    total_frames: int
    n_cuts: int
    keyword_source: str


def view_of(row: Any) -> PlanView:  # noqa: ANN401
    return PlanView(ep.EditPlan.model_validate(row.plan), row.frozen_at is not None)


def summary_of(row: Any) -> PlanSummary:  # noqa: ANN401
    plan = ep.EditPlan.model_validate(row.plan)
    return PlanSummary(
        plan.version,
        row.frozen_at is not None,
        plan.total_frames,
        len(plan.cuts),
        plan.provenance.keyword_source,
    )


async def get_plan(
    session: AsyncSession, user_id: UUID, project_id: UUID, version: int | None
) -> PlanView:
    if await ProjectRepository(session).get(user_id=user_id, project_id=project_id) is None:
        raise NotFound
    plans = PlanRepository(session)
    if version is None:
        row = await plans.latest(user_id=user_id, project_id=project_id)
        if row is None:
            raise Conflict(ConflictReason.NO_PLAN_YET)
    else:
        row = await plans.get_version(user_id=user_id, project_id=project_id, version=version)
        if row is None:
            raise NotFound
    await ProjectRepository(session).touch(user_id=user_id, project_id=project_id)
    await session.commit()
    return view_of(row)


# --- writing (#12) ------------------------------------------------------------------------------


@dataclass(frozen=True)
class PatchResult:
    view: PlanView | None  # a local edit: the new plan
    job_id: UUID | None  # a fetch edit: the replan job


def _refused(exc: Exception) -> Exception:
    """Map a domain refusal to the API's error."""
    if isinstance(exc, LockConflict):
        return LockConflictError(exc.reason)
    if isinstance(exc, PlanOpError):
        return LockConflictError(exc.reason) if exc.lock else ValidationFailed(exc.reason)
    if isinstance(exc, PlanError):
        first = exc.violations[0].rule if exc.violations else None
        return ValidationFailed(exc.reason, first)
    if isinstance(exc, GridError):
        return ValidationFailed(exc.reason)
    if isinstance(exc, NoUsableClips):
        return ValidationFailed("no_usable_clips")
    raise exc


async def apply_patch(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    *,
    base_version: int,
    ops: Sequence[AnyOp],
    publisher: EventPublisher | None,
    enqueuer: Enqueuer,
) -> PatchResult:
    projects = ProjectRepository(session)
    project = await projects.get(user_id=user_id, project_id=project_id)
    if project is None:
        raise NotFound
    latest = await PlanRepository(session).latest(user_id=user_id, project_id=project_id)
    if latest is None:
        raise Conflict(ConflictReason.NO_PLAN_YET)
    if base_version != latest.version:
        raise PlanVersionConflict(latest.version)
    keyword_ops = [o for o in ops if isinstance(o, SetKeywords)]
    if keyword_ops and len(ops) != 1:
        raise ValidationFailed("mixed_ops_not_supported")
    if keyword_ops:
        return await _fetch_edit(
            session, user_id, project, keyword_ops[0], publisher=publisher, enqueuer=enqueuer
        )
    if project.status not in PATCHABLE:
        raise Conflict(ConflictReason.WRONG_STATE)
    return await _local_edit(session, user_id, project, latest, ops, publisher=publisher)


def _flags_only(
    prior: ep.EditPlan, state: ReplanState, version: int, plan_id: UUID, exhausted: bool
) -> BuiltPlan:
    flags = {c.index: c.clip.locked for c in prior.cuts}
    flags.update(dict(state.locks))
    cuts = [
        c.model_copy(update={"clip": c.clip.model_copy(update={"locked": flags[c.index]})})
        for c in prior.cuts
    ]
    plan = prior.model_copy(
        update={"cuts": cuts, "version": version, "plan_id": plan_id, "created_by": "user"}
    )
    return BuiltPlan(with_hash(plan), exhausted, 0, [])


async def _local_edit(
    session: AsyncSession,
    user_id: UUID,
    project: Project,
    latest: Any,  # noqa: ANN401
    ops: Sequence[AnyOp],
    *,
    publisher: EventPublisher | None,
) -> PatchResult:
    basis = await load_basis(session, user_id, project.id)
    prior = ep.EditPlan.model_validate(latest.plan)
    ctx = OpContext(
        song_duration(basis),
        bool(basis.analysis.fallback and "grid" in basis.analysis.beat_map),
        len(prior.cuts),
    )
    frozen = latest.frozen_at is not None
    version, plan_id = (latest.version + 1, new_id()) if frozen else (latest.version, latest.id)
    try:
        state = apply_ops(initial_state(basis), list(ops), ctx)
        if all(isinstance(o, LockClip) for o in ops):  # a flag only: nothing is replanned
            built = _flags_only(
                prior, state, version, plan_id, bool(project.flags.get("pool_exhausted"))
            )
        else:
            built = build(
                basis,
                state,
                version=version,
                plan_id=plan_id,
                llm_model=prior.provenance.llm_model,
                keyword_source=prior.provenance.keyword_source,
                keywords_override=prior.options.keywords_override,
                prior=prior,
                created_by="user",
            )
    except (LockConflict, PlanOpError, PlanError, GridError, NoUsableClips) as exc:
        raise _refused(exc) from exc
    digest = content_hash(built.plan)
    same_cuts = content_hash(built.plan.model_copy(update={"version": latest.version}))
    if bytes(latest.content_hash) in {digest, same_cuts}:  # identical: no new row or version
        return PatchResult(view_of(latest), None)
    plans = PlanRepository(session)
    payload = built.plan.model_dump(mode="json")
    if frozen:
        try:
            await plans.insert(
                user_id=user_id,
                project_id=project.id,
                plan_id=built.plan.plan_id,
                version=built.plan.version,
                schema_version=built.plan.schema_version,
                plan=payload,
                content_hash=digest,
                created_by="user",
            )
        except PlanVersionExists:
            raise PlanVersionConflict(latest.version + 1) from None
    elif not await plans.replace_working(
        user_id=user_id,
        project_id=project.id,
        plan_id=latest.id,
        expected_hash=bytes(latest.content_hash),
        plan=payload,
        content_hash=digest,
        created_by="user",
    ):
        # frozen, or edited by another request, between our read and our write
        raise PlanVersionConflict(latest.version)
    await CandidateRepository(session).mark_selected(
        user_id=user_id,
        project_id=project.id,
        keys={(c.clip.provider, c.clip.provider_id) for c in built.plan.cuts},
    )
    await ProjectRepository(session).update_fields(
        user_id=user_id,
        project_id=project.id,
        # shortcut: the flags are written back whole, so a concurrent flag writer can lose a key;
        # upgrade to a jsonb partial update when a second writer exists
        values={"flags": {**project.flags, "pool_exhausted": built.pool_exhausted}},
    )
    moved = False
    if project.status == ProjectStatus.READY.value:  # the previous render stays downloadable
        moved = await project_state.transition(
            session,
            publisher,
            user_id=user_id,
            project_id=project.id,
            from_=ProjectStatus.READY.value,
            to=ProjectStatus.DRAFT_READY.value,
            commit=False,
        )
    await session.commit()
    if moved:
        await project_state.announce_pending(session, publisher)
    return PatchResult(PlanView(built.plan, frozen=False), None)  # not the identity-mapped row


async def _fetch_edit(
    session: AsyncSession,
    user_id: UUID,
    project: Project,
    op: SetKeywords,
    *,
    publisher: EventPublisher | None,
    enqueuer: Enqueuer,
) -> PatchResult:
    try:
        refuse_keyword_extras(op)
    except PlanOpError as exc:
        raise _refused(exc) from exc
    if project.status == ProjectStatus.RENDERING.value:
        raise Conflict(ConflictReason.RENDER_ACTIVE)  # P6-11: the one job rule
    if project.status != ProjectStatus.DRAFT_READY.value:
        raise Conflict(ConflictReason.WRONG_STATE)
    keywords = clean_keywords(op.keywords)
    if not keywords:
        raise ValidationFailed("keywords_invalid")
    job_id = new_id()
    projects = ProjectRepository(session)
    await projects.update_fields(
        user_id=user_id,
        project_id=project.id,
        values={"options": {**project.options, "keywords_override": keywords}},
    )
    moved = await project_state.transition(
        session,
        publisher,
        user_id=user_id,
        project_id=project.id,
        from_=ProjectStatus.DRAFT_READY.value,
        to=ProjectStatus.PLANNING.value,
        commit=False,
    )
    if not moved:
        await session.rollback()
        raise Conflict(ConflictReason.WRONG_STATE)
    try:
        await JobRepository(session).create(
            user_id=user_id,
            project_id=project.id,
            job_id=job_id,
            stage=JobStage.REPLAN.value,
            queue=JobQueue.FETCH.value,
        )
        await session.commit()  # the worker must see the rows before the message exists
    except IntegrityError:  # uq_jobs_active: a draft, replan or render is already running
        await session.rollback()
        session.info.pop(project_state.PENDING, None)
        raise Conflict(ConflictReason.JOB_ACTIVE) from None
    await project_state.announce_pending(session, publisher)
    # shortcut: a Redis-down send leaves the project planning with an active job (recover with
    # cancel); upgrade: an enqueue failure triggers the cancel recovery itself
    await asyncio.to_thread(enqueuer.send, "replan", str(job_id), str(user_id))
    return PatchResult(None, job_id)


async def restore_keywords_override(session: AsyncSession, user_id: UUID, project_id: UUID) -> None:
    """A replan that ended without a new plan: `options.keywords_override` goes back to what the
    stored plan was built with (the planner reads it from the options), or away. No commit."""
    projects = ProjectRepository(session)
    project = await projects.get(user_id=user_id, project_id=project_id)
    latest = await PlanRepository(session).latest(user_id=user_id, project_id=project_id)
    if project is None or latest is None:
        return
    options = {k: v for k, v in project.options.items() if k != "keywords_override"}
    if kept := latest.plan.get("options", {}).get("keywords_override"):
        options["keywords_override"] = kept
    await projects.update_fields(
        user_id=user_id, project_id=project_id, values={"options": options}
    )

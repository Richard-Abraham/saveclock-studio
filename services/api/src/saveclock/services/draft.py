"""The automatic draft (T-2.10a): ONE job with sequential, timed stages that turns an analysed song
into the first edit plan, or (`replan`) into a new version after new keywords (P5-1).

keywords -> estimate -> search -> vet -> normalize -> plan -> persist. Each stage records its wall
time in `jobs.timings` and announces progress; `cancel_requested` is read between stages and
passed to the footage runner. Every stage is idempotent, so a redelivery after a crash repeats
work but never duplicates a row: the plan, the project's status, the flags and the job's end are
written in one transaction.
"""

import asyncio
import threading
import time
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

import structlog
from redis import Redis

from saveclock.adapters.llm import AnthropicLlm, HashLlm, LlmClient
from saveclock.domain import edit_plan as ep
from saveclock.domain.clip_assign import LockConflict, NoUsableClips, matches
from saveclock.domain.events import FailedEvent
from saveclock.domain.keywords import KeywordSource, summary_from_analysis
from saveclock.domain.plan_hash import content_hash, with_hash
from saveclock.domain.plan_ops import ReplanState
from saveclock.domain.planner import BuiltPlan
from saveclock.domain.ranking import RankedClip, top_k_count
from saveclock.errors import StockUnavailable
from saveclock.ids import new_id
from saveclock.models import ProjectStatus
from saveclock.repositories.candidates import CandidateRepository
from saveclock.repositories.jobs import JobRepository
from saveclock.repositories.plans import PlanRepository
from saveclock.repositories.projects import ProjectRepository
from saveclock.services import plans, project_state
from saveclock.services.analysis import JobCanceled
from saveclock.services.context import WorkerContext, end_unwanted
from saveclock.services.events import ProgressEmitter, ProgressTicker
from saveclock.services.footage import (
    FootageDeps,
    build_footage_deps,
    effective_pixabay,
    search,
    vet_and_rank,
)
from saveclock.services.keywords import KeywordDeps, KeywordResult, resolve_keywords
from saveclock.services.normalize import normalize_topk

log = structlog.get_logger()

Mode = Literal["draft", "replan"]
# (stage, the stepper step it belongs to, the fraction of that step at its start)
STAGES: tuple[tuple[str, str, float], ...] = (
    ("keywords", "choosing_clips", 0.0),
    ("estimate", "choosing_clips", 0.1),
    ("search", "choosing_clips", 0.15),
    ("vet", "choosing_clips", 0.4),
    ("normalize", "building_draft", 0.0),
    ("plan", "building_draft", 0.7),
    ("persist", "building_draft", 0.9),
)
CANCEL_POLL_S = 1.0
EXPECTED_S = {"search": 20.0, "vet": 40.0, "normalize": 40.0}  # the ticker's pace only


def build_llm(ctx: WorkerContext) -> LlmClient | None:
    s = ctx.settings
    if s.fake_llm:
        return HashLlm()
    if s.anthropic_api_key is not None:
        return AnthropicLlm(s.anthropic_api_key.get_secret_value(), s.llm_model)
    return None


@dataclass
class _Run:
    ctx: WorkerContext
    user_id: UUID
    job_id: UUID
    project_id: UUID
    emitter: ProgressEmitter
    timings: list[dict[str, int | str]] = field(default_factory=list)
    started: float = field(default_factory=time.monotonic)
    current: tuple[str, float] | None = None
    canceled: threading.Event = field(default_factory=threading.Event)

    async def cancelled(self) -> bool:
        async with self.ctx.sessionmaker() as session:
            return await JobRepository(session).cancel_requested(
                user_id=self.user_id, job_id=self.job_id
            )

    @asynccontextmanager
    async def stage(self, name: str) -> AsyncIterator[None]:
        """Check for a cancel, announce the stage, run it under a ticker, record its time."""
        if await self.cancelled():
            raise JobCanceled
        step, fraction = next((s, f) for n, s, f in STAGES if n == name)
        await self.emitter.aemit(step, fraction, force=True)
        began = time.monotonic()
        self.current = (name, began)
        try:
            if name in EXPECTED_S:
                with ProgressTicker(
                    self.emitter, step, expected_s=EXPECTED_S[name]
                ):  # one blocking call, alive
                    yield
            else:
                yield
        finally:
            self.current = None
            self.timings.append({"stage": name, "ms": int((time.monotonic() - began) * 1000)})

    def finished(self) -> dict[str, object]:
        """The timings so far plus the stage that is running (persist writes them in its own
        transaction, before its `stage` block has ended)."""
        stages = list(self.timings)
        if self.current is not None:
            name, began = self.current
            stages.append({"stage": name, "ms": int((time.monotonic() - began) * 1000)})
        return {"stages": stages, "total_ms": int((time.monotonic() - self.started) * 1000)}


async def run_draft(ctx: WorkerContext, job_id: UUID, user_id: UUID, *, mode: Mode) -> None:
    """Actor body. A permanent failure is a normal return after the state is written; only
    transient errors raise (Dramatiq retries them, and the failure hook ends the job)."""
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
    if project is None or project.status != ProjectStatus.PLANNING.value:
        await end_unwanted(ctx, user_id, job_id)
        return
    run = _Run(ctx, user_id, job_id, project_id, ProgressEmitter(ctx.publisher, project_id))
    try:
        await _run(run, mode)
    except JobCanceled:
        await end_unwanted(ctx, user_id, job_id)
    except LockConflict:
        await _back_to_draft(run, "lock_conflict", "lock_conflict")
        if ctx.publisher is not None:
            await ctx.publisher.publish(project_id, FailedEvent("replan", "lock_conflict", False))
    except (StockUnavailable, NoUsableClips) as exc:
        reason = "no_usable_clips" if isinstance(exc, NoUsableClips) else "stock_unavailable"
        if mode == "replan":  # the previous plan is untouched: the owner keeps editing it
            await _back_to_draft(run, "stock_unavailable", reason)
        else:
            await _fail_plan(run, reason)


async def _run(run: _Run, mode: Mode) -> None:
    ctx, user_id, project_id = run.ctx, run.user_id, run.project_id
    async with ctx.sessionmaker() as session:
        basis = await plans.load_basis(session, user_id, project_id)
    state = plans.initial_state(basis)
    redis: Redis = Redis.from_url(ctx.settings.redis_url.get_secret_value())
    watch: asyncio.Task[None] | None = None
    deps: FootageDeps | None = None
    try:
        async with run.stage("keywords"):
            keywords = await asyncio.to_thread(_resolve_keywords, ctx, redis, basis)
        async with run.stage("estimate"):
            cuts = await asyncio.to_thread(plans.estimate_cuts, basis, state)
        watch = asyncio.create_task(_watch_cancel(run))
        deps = build_footage_deps(
            ctx,
            redis,
            pixabay_on=await effective_pixabay(ctx, user_id),
            cancel=run.canceled.is_set,
            seed=plans.seed_of(project_id),
        )
        async with run.stage("search"):
            await search(deps, user_id=user_id, project_id=project_id, keywords=keywords.keywords)
        async with run.stage("vet"):
            async with ctx.sessionmaker() as session:
                rows = await CandidateRepository(session).list_for_project(
                    user_id=user_id, project_id=project_id
                )
            vetted = await vet_and_rank(
                deps, user_id=user_id, project_id=project_id, candidates=rows
            )
        async with run.stage("normalize"):
            await _normalize(run, deps, vetted.ranked, keywords.keywords, cuts)
    finally:
        if watch is not None:
            watch.cancel()
        if deps is not None:
            deps.close()  # the providers' shared HTTP client
        await asyncio.to_thread(redis.close)
    async with run.stage("plan"):
        async with ctx.sessionmaker() as session:
            basis = await plans.load_basis(session, user_id, project_id)
        built = await asyncio.to_thread(_plan, ctx, basis, state, keywords)
    async with run.stage("persist"):
        version = await _persist(run, basis, built, keywords)
    if version is None:  # canceled while we worked: the API already moved the project
        await end_unwanted(ctx, user_id, run.job_id)
        return
    await run.emitter.draft_ready(version)
    log.info("draft.done", mode=mode, version=version, cuts=len(built.plan.cuts))


async def _watch_cancel(run: _Run) -> None:
    """Polls the job's cancel flag into a thread-safe event: the footage runner asks `cancel()`
    from the event loop and from threads, and a database probe would deadlock on the loop."""
    while not run.canceled.is_set():
        if await run.cancelled():
            run.canceled.set()
            return
        await asyncio.sleep(CANCEL_POLL_S)


def _resolve_keywords(ctx: WorkerContext, redis: Redis, basis: plans.Basis) -> KeywordResult:
    a, project = basis.analysis, basis.project
    sections = [(str(s["label"]), float(s["end_s"]) - float(s["start_s"])) for s in a.sections]
    summary = summary_from_analysis(
        float(a.tempo_bpm),
        a.energy_curve,
        sections,
        style=str(project.options.get("style", "default")),
        vibe=project.options.get("vibe"),
    )
    deps = KeywordDeps(ctx.settings, redis, build_llm(ctx))
    return resolve_keywords(deps, summary, project.options)


async def _normalize(
    run: _Run, deps: FootageDeps, ranked: Sequence[RankedClip], keywords: Sequence[str], cuts: int
) -> None:
    """The top K for these keywords, minus the clips an earlier run already normalized (a crash
    redelivery) or that an earlier keyword set left in the pool: a replan still gets its own."""
    async with run.ctx.sessionmaker() as session:
        pool = await CandidateRepository(session).list_pool(
            user_id=run.user_id, project_id=run.project_id
        )

    def wanted(query: str) -> bool:
        return any(matches(query, kw) for kw in keywords)

    ready = {(c.provider, c.provider_id) for c in pool}
    have = sum(1 for c in pool if wanted(c.query))
    todo = [r for r in ranked if (r.provider, r.provider_id) not in ready and wanted(r.query)]
    need = max(0, top_k_count(cuts, run.ctx.settings.topk_factor) - have)
    if need and todo:
        await normalize_topk(
            deps,
            user_id=run.user_id,
            project_id=run.project_id,
            ranked=todo,
            cuts=need,
            factor=1.0,
        )


def _plan(
    ctx: WorkerContext, basis: plans.Basis, state: ReplanState, keywords: KeywordResult
) -> BuiltPlan:
    latest = basis.latest
    prior = ep.EditPlan.model_validate(latest.plan) if latest is not None else None
    frozen = latest is not None and latest.frozen_at is not None
    version = 1 if latest is None else latest.version + (1 if frozen else 0)
    plan_id = latest.id if latest is not None and not frozen else new_id()
    return plans.build(
        basis,
        state,
        version=version,
        plan_id=plan_id,
        llm_model=ctx.settings.llm_model if keywords.source is KeywordSource.LLM else None,
        keyword_source=keywords.source.value,
        keywords_override=basis.project.options.get("keywords_override") or None,
        prior=prior,
    )


async def _persist(
    run: _Run, basis: plans.Basis, built: BuiltPlan, keywords: KeywordResult
) -> int | None:
    """Plan, selection, flags, the status change and the job's end, in one transaction."""
    ctx, user_id, project_id = run.ctx, run.user_id, run.project_id
    plan = built.plan
    async with ctx.sessionmaker() as session:
        repo = PlanRepository(session)
        latest = await repo.latest(user_id=user_id, project_id=project_id)
        reuse = latest is not None and latest.frozen_at is None
        version = 1 if latest is None else latest.version + (0 if reuse else 1)
        plan_id = latest.id if latest is not None and reuse else plan.plan_id
        if (plan.version, plan.plan_id) != (version, plan_id):  # the stored plans moved on
            plan = with_hash(plan.model_copy(update={"version": version, "plan_id": plan_id}))
        payload = plan.model_dump(mode="json")
        digest = content_hash(plan)
        if latest is not None and reuse:
            assert await repo.replace_working(  # noqa: S101 - nobody freezes a planning project
                user_id=user_id,
                project_id=project_id,
                plan_id=latest.id,
                plan=payload,
                content_hash=digest,
                created_by="planner",
            )
        else:
            await repo.insert(
                user_id=user_id,
                project_id=project_id,
                plan_id=plan_id,
                version=version,
                schema_version=plan.schema_version,
                plan=payload,
                content_hash=digest,
                created_by="planner",
            )
        await CandidateRepository(session).mark_selected(
            user_id=user_id,
            project_id=project_id,
            keys={(c.clip.provider, c.clip.provider_id) for c in plan.cuts},
        )
        project = await ProjectRepository(session).get(user_id=user_id, project_id=project_id)
        flags = {
            **(project.flags if project is not None else {}),
            "pool_exhausted": built.pool_exhausted,
            "degraded_keywords": keywords.degraded,
        }
        await ProjectRepository(session).update_fields(
            user_id=user_id, project_id=project_id, values={"flags": flags}
        )
        moved = await project_state.transition(
            session,
            ctx.publisher,
            user_id=user_id,
            project_id=project_id,
            from_=ProjectStatus.PLANNING.value,
            to=ProjectStatus.DRAFT_READY.value,
            commit=False,
        )
        if not moved:
            await session.rollback()
            session.info.pop(project_state.PENDING, None)
            return None
        await JobRepository(session).finish_with(
            user_id=user_id, job_id=run.job_id, timings=run.finished()
        )
        await session.commit()
        await project_state.announce_pending(session, ctx.publisher)
    return version


async def _fail_plan(run: _Run, reason: str) -> None:
    """planning -> failed_plan; the job's error is the catalogue's `stock_unavailable`."""
    async with run.ctx.sessionmaker() as session:
        await project_state.transition(
            session,
            run.ctx.publisher,
            user_id=run.user_id,
            project_id=run.project_id,
            from_=ProjectStatus.PLANNING.value,
            to=ProjectStatus.FAILED_PLAN.value,
            reason=reason,
            commit=False,
        )
        await JobRepository(session).fail(
            user_id=run.user_id, job_id=run.job_id, error_code="stock_unavailable"
        )
        await session.commit()
        await project_state.announce_pending(session, run.ctx.publisher)


async def _back_to_draft(run: _Run, error_code: str, reason: str) -> None:
    """A replan that could not finish: the previous plan stays (planning -> draft_ready)."""
    async with run.ctx.sessionmaker() as session:
        await project_state.transition(
            session,
            run.ctx.publisher,
            user_id=run.user_id,
            project_id=run.project_id,
            from_=ProjectStatus.PLANNING.value,
            to=ProjectStatus.DRAFT_READY.value,
            reason=reason,
            commit=False,
        )
        await JobRepository(session).fail(
            user_id=run.user_id, job_id=run.job_id, error_code=error_code
        )
        await session.commit()
        await project_state.announce_pending(session, run.ctx.publisher)

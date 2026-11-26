"""Beat, energy and section analysis of the canonical audio (T-2.2, T-2.3, T-2.24).

The raw model output is always kept in `beat_map["raw"]`, so a later half/double or "use detected
beats" recomputes without re-inference (ARCH §5 `set_tempo_octave`). Everything heavy runs in a
worker thread under the Redis heavy lock; the actor is a thin wrapper around `analyze_project`.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.adapters import dsp
from saveclock.adapters.beat_this import BeatModel, BeatThisModel, FakeBeatModel
from saveclock.adapters.blobstore.blob_keys import canonical_key
from saveclock.adapters.heavy_lock import HeavyLock
from saveclock.adapters.models import ModelIntegrityError, verified_path
from saveclock.config import ANALYZE_WAIT_S, Settings
from saveclock.domain import confidence, energy
from saveclock.domain.beat_grid import clamp_octave, fold_downbeats, median_bpm
from saveclock.domain.segment import select_segment
from saveclock.errors import Conflict, ConflictReason, NotFound
from saveclock.models import Analysis, Fallback, JobQueue, JobStage, Project, ProjectStatus
from saveclock.repositories.analyses import AnalysisRepository
from saveclock.repositories.jobs import JobRepository
from saveclock.repositories.projects import ProjectRepository
from saveclock.services import project_state
from saveclock.services.autotune import effective, host_facts
from saveclock.services.context import WorkerContext, cancel_probe, end_unwanted, hand_off
from saveclock.services.events import ProgressEmitter, ProgressTicker

log = structlog.get_logger()

CONFIDENCE_VERSION = 1  # bump when the weights change (P4-10)
LOW_CONFIDENCE = 0.5
ANALYZE_EXPECTED_S = 30.0  # a typical song's beat tracking; only the tick's pace depends on it


class JobCanceled(Exception):  # a signal, not an error
    """The owner canceled the project while the job ran."""


class NoBeatsFound(ValueError):
    """The model found fewer than two beats: there is no grid to build on."""


@dataclass(frozen=True)
class Computed:
    values: dict[str, Any]
    tempo_bpm: Decimal
    low_confidence: bool


def _checked(cancel: Callable[[], bool]) -> None:
    if cancel():
        raise JobCanceled


def compute_analysis(
    signal: dsp.FloatArray,
    sr: int,
    model: BeatModel,
    *,
    length_s: int,
    cancel: Callable[[], bool],
    decode_ms: int = 0,
) -> Computed:
    """Pure with respect to the database: audio in, the `analyses` columns out."""
    started = time.monotonic()
    duration_s = len(signal) / sr
    _checked(cancel)
    t = time.monotonic()
    raw_beats, raw_downbeats = model.infer(signal, sr)
    beat_ms = int((time.monotonic() - t) * 1000)
    if len(raw_beats) < 2:  # noqa: PLR2004
        msg = "fewer than two beats"
        raise NoBeatsFound(msg)
    _checked(cancel)
    beats, octave = clamp_octave(raw_beats)
    downbeats, derived = fold_downbeats(raw_downbeats, beats)

    t = time.monotonic()
    curve = energy.energy_curve(dsp.rms_db(signal, sr))
    bars = energy.bar_energy(curve, downbeats)
    secs = energy.sections(energy.levels(bars), downbeats)
    segment = select_segment(bars, downbeats, duration_s, min(length_s, int(duration_s)))
    segment_ms = int((time.monotonic() - t) * 1000)

    _checked(cancel)
    env, rate = dsp.onset_envelope(signal, sr)
    onset_bpm = dsp.onset_tempo(env, rate)
    sig = confidence.signals(
        beats,
        downbeats,
        onset_bpm,
        dsp.onset_at_beats(env, rate, beats),
        dsp.audio_condition(signal, sr),
    )
    conf = confidence.score(sig)
    beat_map: dict[str, Any] = {
        "raw": {"beats_s": raw_beats, "downbeats_s": raw_downbeats},
        "beats_s": beats,
        "downbeats_s": downbeats,
        "downbeats_derived": derived,
        "onset_tempo_bpm": onset_bpm,
        "segment": asdict(segment),
        "confidence": {"reasons": conf.reasons, "signals": sig, "version": CONFIDENCE_VERSION},
    }
    fallback: str | None = None
    if conf.score < LOW_CONFIDENCE:
        fallback = Fallback.ENERGY_GRID.value
        grid = confidence.energy_grid(dsp.onset_peaks(env, rate))
        beat_map["grid"] = {"kind": fallback, "beats_s": grid}
    bpm = median_bpm(beats) or 0.0
    values = {
        "model": model.name,
        "model_version": model.version,
        "tempo_octave_adjust": octave,
        "beat_confidence": conf.score,
        "fallback": fallback,
        "beat_map": beat_map,
        "sections": [asdict(s) for s in secs],
        "energy_curve": [round(v, 3) for v in curve],
        "waveform_peaks": dsp.waveform_peaks(signal),
        "low_confidence_ranges": [list(r) for r in confidence.low_confidence_ranges(beats)],
        "timing": {
            "decode_ms": decode_ms,
            "beat_this_ms": beat_ms,
            "segment_ms": segment_ms,
            "total_ms": decode_ms + int((time.monotonic() - started) * 1000),
            "confidence_version": CONFIDENCE_VERSION,
        },
    }
    return Computed(values, Decimal(str(round(bpm, 2))), conf.band == "low")


_MODELS: dict[tuple[bool, str], BeatModel] = {}


def get_model(settings: Settings) -> BeatModel:
    """One model per process, built on first use (not at import)."""
    key = (settings.fake_ml, settings.beat_this_checkpoint)
    if key not in _MODELS:
        if settings.fake_ml:
            _MODELS[key] = FakeBeatModel()
        else:
            name = f"beat_this-{settings.beat_this_checkpoint}"
            checkpoint = verified_path(settings.models_dir, name)  # ModelIntegrityError: no retry
            tuning = effective(settings, host_facts())
            _MODELS[key] = BeatThisModel(checkpoint, tuning.torch_threads)
    return _MODELS[key]


def _compute_blocking(
    ctx: WorkerContext, project_id: UUID, length_s: int, cancel: Callable[[], bool]
) -> Computed:
    settings = ctx.settings
    model = get_model(settings)
    redis: Redis = Redis.from_url(settings.redis_url.get_secret_value())
    try:
        lock = HeavyLock(redis, effective(settings, host_facts()).heavy, settings.heavy_ttl_s)
        with lock.hold(ANALYZE_WAIT_S):  # HeavyLockTimeout is retryable, inside the actor limit
            t = time.monotonic()
            signal, sr = dsp.decode_mono(ctx.blobs.local_path(canonical_key(project_id)))
            decode_ms = int((time.monotonic() - t) * 1000)
            return compute_analysis(
                signal, sr, model, length_s=length_s, cancel=cancel, decode_ms=decode_ms
            )
    finally:
        redis.close()


async def _end_failed(
    ctx: WorkerContext, user_id: UUID, job_id: UUID, project_id: UUID, reason: str
) -> None:
    async with ctx.sessionmaker() as session:
        await project_state.transition(
            session,
            ctx.publisher,
            user_id=user_id,
            project_id=project_id,
            from_=ProjectStatus.ANALYZING.value,
            to=ProjectStatus.FAILED_ANALYSIS.value,
            reason=reason,
            commit=False,
        )
        await JobRepository(session).fail(
            user_id=user_id, job_id=job_id, error_code="internal_error"
        )
        await session.commit()
        await project_state.announce_pending(session, ctx.publisher)


async def analyze_project(ctx: WorkerContext, job_id: UUID, user_id: UUID) -> None:
    """Actor body. Permanent failures are a normal return; only transient errors raise."""
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
        status == ProjectStatus.PLANNING.value
    ):  # redelivery after the transition: finish the hand-off
        await _hand_off_to_draft(ctx, user_id, job_id, project_id, {"redelivered": True})
        return
    if project is None or status != ProjectStatus.ANALYZING.value:
        await end_unwanted(ctx, user_id, job_id)
        return
    cancel = cancel_probe(ctx, user_id, job_id)
    emitter = ProgressEmitter(ctx.publisher, project_id)
    try:
        await asyncio.to_thread(get_model, ctx.settings)  # fail fast on a bad weights file
        with ProgressTicker(emitter, "finding_beat", expected_s=ANALYZE_EXPECTED_S):
            result = await asyncio.to_thread(
                _compute_blocking,
                ctx,
                project_id,
                int(project.options.get("duration", 30)),
                cancel,
            )
    except JobCanceled:
        await end_unwanted(ctx, user_id, job_id)
        return
    except ModelIntegrityError:
        log.error("analyze.model_integrity")
        await _end_failed(ctx, user_id, job_id, project_id, "model_integrity")
        return
    except NoBeatsFound:
        await _end_failed(ctx, user_id, job_id, project_id, "no_beats_found")
        return
    await emitter.aemit("finding_beat", 1.0, force=True)
    async with ctx.sessionmaker() as session:
        projects = ProjectRepository(session)
        await AnalysisRepository(session).upsert(
            user_id=user_id,
            project_id=project_id,
            tempo_bpm=result.tempo_bpm,
            values=result.values,
        )
        await projects.update_fields(
            user_id=user_id,
            project_id=project_id,
            values={"flags": {**project.flags, "low_confidence": result.low_confidence}},
        )
        moved = await project_state.transition(
            session,
            ctx.publisher,
            user_id=user_id,
            project_id=project_id,
            from_=ProjectStatus.ANALYZING.value,
            to=ProjectStatus.PLANNING.value,
            commit=False,
        )
        await session.commit()
        await project_state.announce_pending(session, ctx.publisher)
        current = await projects.get(user_id=user_id, project_id=project_id)
    if not moved and (current is None or current.status == ProjectStatus.CANCELED.value):
        await end_unwanted(ctx, user_id, job_id)
        return
    await _hand_off_to_draft(ctx, user_id, job_id, project_id, result.values["timing"])


async def _hand_off_to_draft(
    ctx: WorkerContext, user_id: UUID, job_id: UUID, project_id: UUID, timings: dict[str, Any]
) -> None:
    await hand_off(
        ctx,
        user_id,
        job_id,
        project_id=project_id,
        next_stage=JobStage.DRAFT,
        next_queue=JobQueue.FETCH,
        actor="build_draft",
        timings=timings,
    )


# --- read side (API) --------------------------------------------------------------------------


@dataclass(frozen=True)
class AnalysisView:
    analysis: Analysis
    project: Project
    beats_s: list[float]
    downbeats_s: list[float]


async def get_analysis(session: AsyncSession, user_id: UUID, project_id: UUID) -> AnalysisView:
    project = await ProjectRepository(session).get(user_id=user_id, project_id=project_id)
    if project is None:
        raise NotFound
    analysis = await AnalysisRepository(session).get_by_project(
        user_id=user_id, project_id=project_id
    )
    if analysis is None:
        raise Conflict(ConflictReason.NOT_READY)
    await ProjectRepository(session).touch(user_id=user_id, project_id=project_id)
    await session.commit()
    bm = analysis.beat_map
    beats = bm["grid"]["beats_s"] if analysis.fallback and "grid" in bm else bm["beats_s"]
    return AnalysisView(analysis, project, list(beats), list(bm["downbeats_s"]))

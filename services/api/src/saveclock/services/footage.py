"""Find, fetch, vet and rank stock footage (T-2.6, T-2.7, T-2.18). Plan 006 chains these into the
draft job; here each stage is a service function with its dependencies handed in.

Stages are functions, not actors (P5-1): one `build_draft` job owns the time budget. Blocking work
(HTTP, FFmpeg, OpenCV, the model) runs in worker threads; database writes stay on the event loop.
A heavy slot is taken once per unit of work (one candidate's analysis), never for a whole batch.
"""

import asyncio
import io
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

import httpx
import numpy as np
import structlog
from redis import Redis

from saveclock.adapters.blobstore.blob_keys import emb_key, raw_key
from saveclock.adapters.ffmpeg import FfCanceled, FfError, FfTimeout, probe_stock, sample_frames
from saveclock.adapters.heavy_lock import HeavyLock
from saveclock.adapters.models import verified_group
from saveclock.adapters.safe_http import DownloadRefused
from saveclock.adapters.scenedetect import detect_cuts
from saveclock.adapters.siglip import FakeRanker, ImageTextRanker, SigLipRanker
from saveclock.adapters.stock.download import Downloader, allowed_hosts
from saveclock.adapters.stock.fake import FakeStockProvider
from saveclock.adapters.stock.limits import (
    CircuitBreaker,
    FixedWindowLimiter,
    ProviderHttp,
    SearchCache,
)
from saveclock.adapters.stock.pexels import PexelsProvider
from saveclock.adapters.stock.pixabay import PixabayProvider
from saveclock.adapters.stock.port import StockClip, StockProvider
from saveclock.adapters.vision import laplacian_variance
from saveclock.config import FOOTAGE_WAIT_S, Settings
from saveclock.domain.keywords import broaden
from saveclock.domain.ranking import RankedClip, near_duplicates, rank
from saveclock.domain.sampling import clip_score, frame_scores, mean_vector, normalize, sample_count
from saveclock.domain.stock_rules import (
    MAX_DOWNLOAD_BYTES,
    ClipMeta,
    RejectReason,
    check_candidate,
    is_blurry,
)
from saveclock.domain.windows import Window, best_window
from saveclock.errors import StockUnavailable
from saveclock.ids import new_id
from saveclock.models import ClipCandidate, ClipStatus
from saveclock.repositories.candidates import CandidateRepository, NewCandidate
from saveclock.repositories.users import UserRepository
from saveclock.services.analysis import JobCanceled
from saveclock.services.autotune import effective, host_facts
from saveclock.services.context import WorkerContext
from saveclock.services.scratch import scratch_dir

log = structlog.get_logger()

SIGLIP_GROUP = "siglip2-base-patch16-224"
PER_KEYWORD = 40
ENOUGH = 6  # usable candidates for a keyword before the broadening ladder stops (ARCH §16)
YIELD_MIN_CLIPS = 20  # QM-032: a keyword "yields" with this many portrait clips at >= 1080p
YIELD_MIN_WIDTH = 1080
DONE_STATUSES = frozenset({ClipStatus.RANKED, ClipStatus.NORMALIZED, ClipStatus.SELECTED})
REJECTED_STATUSES = frozenset({ClipStatus.REJECTED_CUT, ClipStatus.REJECTED_QUALITY})
PERMANENT_DOWNLOAD_REFUSALS = frozenset(
    {
        "content_type",
        "not_mp4",
        "http_status",
        "scheme",
        "host_not_allowed",
        "address",
        "port",
        "redirect",
        "too_many_redirects",
    }
)


@dataclass(frozen=True)
class FootageDeps:
    ctx: WorkerContext
    providers: tuple[StockProvider, ...]  # Pexels first; Pixabay only while it is switched on
    ranker: ImageTextRanker
    heavy: HeavyLock
    cancel: Callable[[], bool] | None = None
    fetch_concurrency: int = 4
    seed: int | str = 0


@dataclass(frozen=True)
class SearchResult:
    added: int  # new candidate rows
    usable: dict[str, int]  # per keyword: usable candidates found
    search_yield: float  # QM-032: share of keywords with >= 20 portrait clips at >= 1080p


@dataclass(frozen=True)
class VetResult:
    ranked: list[RankedClip]
    rejected: dict[str, int] = field(default_factory=dict)  # by reason
    skipped: int = 0  # transient failures: left as they were, retried by the next run
    near_duplicates: list[tuple[str, str]] = field(default_factory=list)


def _meta(clip: StockClip) -> ClipMeta:
    return ClipMeta(clip.width, clip.height, clip.duration_s, clip.fps, clip.file_size)


def _query_providers(
    providers: Sequence[StockProvider], query: str, per_page: int
) -> tuple[list[StockClip], StockUnavailable | None]:
    """The first provider, then the next ones only while fewer than ENOUGH usable clips came."""
    clips: list[StockClip] = []
    error: StockUnavailable | None = None
    for provider in providers:
        try:
            clips += provider.search(query, page=1, per_page=per_page)
        except StockUnavailable as exc:
            error = exc
        if sum(check_candidate(_meta(c)) is None for c in clips) >= ENOUGH:
            break
    return clips, error


async def search(
    deps: FootageDeps,
    *,
    user_id: UUID,
    project_id: UUID,
    keywords: Sequence[str],
    fallback: Sequence[str] = (),
    per_keyword: int = PER_KEYWORD,
) -> SearchResult:
    """Search every keyword (and its broadening ladder while it has few usable clips), keep what
    passes the cheap provider-metadata rules and store it as `found` candidates."""
    rows: list[NewCandidate] = []
    seen: set[tuple[str, str]] = set()
    usable: dict[str, int] = {}
    yielded = 0
    last_error: StockUnavailable | None = None
    for keyword in keywords:
        count = 0
        for position, query in enumerate(broaden(keyword, fallback)):
            clips, error = await asyncio.to_thread(
                _query_providers, deps.providers, query, per_keyword
            )
            last_error = error or last_error
            if position == 0 and (
                sum(c.height > c.width and c.width >= YIELD_MIN_WIDTH for c in clips)
                >= YIELD_MIN_CLIPS
            ):
                yielded += 1
            for clip in clips:
                key = (clip.provider, clip.provider_id)
                if check_candidate(_meta(clip)) is not None or key in seen:
                    continue
                seen.add(key)
                count += 1
                rows.append(
                    NewCandidate(
                        clip.provider,
                        clip.provider_id,
                        query,
                        clip.page_url,
                        clip.author,
                        clip.author_url,
                        clip.license,
                        clip.width,
                        clip.height,
                        clip.duration_s,
                        clip.fps,
                        clip.file_url,
                    )
                )
            if count >= ENOUGH:
                break
        usable[keyword] = count
    if not rows and last_error is not None:
        raise last_error
    async with deps.ctx.sessionmaker() as session:
        added = await CandidateRepository(session).upsert_found(
            user_id=user_id, project_id=project_id, found=rows
        )
        await session.commit()
    share = yielded / len(keywords) if keywords else 0.0
    log.info("footage.search", keywords=len(keywords), found=len(rows), added=added, yield_=share)
    return SearchResult(added, usable, share)


# --- vetting and ranking ---------------------------------------------------------------------


@dataclass(frozen=True)
class _Reject:
    status: ClipStatus
    reason: RejectReason


@dataclass(frozen=True)
class _Analysed:
    window: Window
    score: float
    scores: list[float]
    mean_embedding: tuple[float, ...]
    embeddings: list[list[float]]


def _to_clip(row: ClipCandidate) -> StockClip:
    return StockClip(
        provider=row.provider,
        provider_id=row.provider_id,
        page_url=row.page_url,
        author=row.author,
        author_url=row.author_url,
        license=row.license,
        width=int(row.width or 0),
        height=int(row.height or 0),
        duration_s=float(row.duration_s or 0),
        fps=row.fps,
        file_url=row.download_url or "",
    )


class Keyed(Protocol):
    """A candidate row or a ranked clip: anything that names its provider and provider id."""

    @property
    def provider(self) -> str: ...

    @property
    def provider_id(self) -> str: ...


async def mark_candidate(
    deps: FootageDeps,
    user_id: UUID,
    project_id: UUID,
    row: Keyed,
    **values: Any,  # noqa: ANN401
) -> None:
    async with deps.ctx.sessionmaker() as session:
        await CandidateRepository(session).mark(
            user_id=user_id,
            project_id=project_id,
            provider=row.provider,
            provider_id=row.provider_id,
            **values,
        )
        await session.commit()


def _reject_values(reject: _Reject) -> dict[str, Any]:
    return {"status": reject.status.value, "reject_reason": reject.reason.value}


def _canceled(deps: FootageDeps) -> None:
    if deps.cancel is not None and deps.cancel():
        raise JobCanceled


def _download(deps: FootageDeps, row: ClipCandidate) -> _Reject | None:
    """Fetch the source clip unless we already have it. A refusal that is a property of the file
    rejects the candidate; a network problem is transient (the caller skips it)."""
    ctx = deps.ctx
    key = raw_key(row.project_id, row.provider, row.provider_id)
    if ctx.blobs.exists(key):
        return None
    if not row.download_url:
        return _Reject(ClipStatus.REJECTED_QUALITY, RejectReason.FFPROBE_FAILED)
    provider = next((p for p in deps.providers if p.name == row.provider), None)
    if provider is None:
        return _Reject(ClipStatus.REJECTED_QUALITY, RejectReason.FFPROBE_FAILED)
    try:
        provider.download(
            _to_clip(row), ctx.blobs, key, max_bytes=MAX_DOWNLOAD_BYTES, cancel=deps.cancel
        )
    except DownloadRefused as exc:
        if exc.reason == "canceled":
            raise JobCanceled from exc
        if exc.reason == "too_large":
            return _Reject(ClipStatus.REJECTED_QUALITY, RejectReason.TOO_LARGE)
        if exc.reason in PERMANENT_DOWNLOAD_REFUSALS:
            return _Reject(ClipStatus.REJECTED_QUALITY, RejectReason.FFPROBE_FAILED)
        raise
    return None


def _analyse(
    deps: FootageDeps, row: ClipCandidate, duration_s: float, text_vec: Sequence[float]
) -> _Analysed | _Reject:
    """Cut detection, window, frame sampling, blur check and embeddings, under one heavy slot."""
    ctx = deps.ctx
    raw = ctx.blobs.local_path(raw_key(row.project_id, row.provider, row.provider_id))
    with deps.heavy.hold(FOOTAGE_WAIT_S):
        window = best_window(detect_cuts(raw), duration_s)
        if window is None:
            return _Reject(ClipStatus.REJECTED_CUT, RejectReason.NO_CUT_FREE_WINDOW)
        with scratch_dir(ctx.settings.scratch_root, new_id()) as tmp:
            frames = sample_frames(
                ctx.tools, raw, tmp, window.start_s, sample_count(window), cancel=deps.cancel
            )
            if not frames:
                return _Reject(ClipStatus.REJECTED_QUALITY, RejectReason.FFPROBE_FAILED)
            if is_blurry(laplacian_variance(frames)):
                return _Reject(ClipStatus.REJECTED_QUALITY, RejectReason.BLURRY)
            vectors = deps.ranker.embed_images(frames)
    scores = frame_scores(vectors, text_vec)
    mean = mean_vector([normalize(v) for v in vectors])
    return _Analysed(window, clip_score(scores), scores, mean, vectors)


def _store_embeddings(deps: FootageDeps, row: ClipCandidate, vectors: list[list[float]]) -> None:
    """Kept so a re-rank against new keywords needs no new frames (P5-7). An intermediate."""
    buf = io.BytesIO()
    np.save(buf, np.asarray(vectors, dtype=np.float32))
    deps.ctx.blobs.put(
        emb_key(row.project_id, row.provider, row.provider_id), [buf.getvalue()], max_bytes=1 << 24
    )


def _stored_ranked(deps: FootageDeps, row: ClipCandidate) -> RankedClip:
    """A candidate vetted by an earlier run, rebuilt from its row (and its embeddings if kept)."""
    mean: tuple[float, ...] = ()
    key = emb_key(row.project_id, row.provider, row.provider_id)
    if deps.ctx.blobs.exists(key):
        data = np.load(io.BytesIO(b"".join(deps.ctx.blobs.open(key))), allow_pickle=False)
        mean = mean_vector([normalize([float(x) for x in v]) for v in data])
    frames = int(row.mezz_frames or 0)
    window = Window(float(row.window_start_s or 0), frames / 30)
    frame_scores_json = row.frame_scores if isinstance(row.frame_scores, dict) else {}
    return RankedClip(
        row.provider,
        row.provider_id,
        str(frame_scores_json.get("query", row.query)),
        float(row.score or 0.0),
        window,
        mean,
    )


async def _vet_one(
    deps: FootageDeps,
    user_id: UUID,
    project_id: UUID,
    row: ClipCandidate,
    text_vectors: dict[str, list[float]],
) -> RankedClip | _Reject | None:
    _canceled(deps)
    rejected = await asyncio.to_thread(_download, deps, row)
    if rejected is not None:
        await mark_candidate(deps, user_id, project_id, row, **_reject_values(rejected))
        return rejected
    await mark_candidate(deps, user_id, project_id, row, status=ClipStatus.DOWNLOADED.value)
    key = raw_key(row.project_id, row.provider, row.provider_id)
    try:
        probe = await asyncio.to_thread(probe_stock, deps.ctx.tools, deps.ctx.blobs.local_path(key))
    except FfCanceled as exc:
        raise JobCanceled from exc
    except FfTimeout:
        return None  # transient: stays `downloaded`
    except FfError:
        reject = _Reject(ClipStatus.REJECTED_QUALITY, RejectReason.FFPROBE_FAILED)
        await mark_candidate(deps, user_id, project_id, row, **_reject_values(reject))
        return reject
    why = check_candidate(
        ClipMeta(probe.width, probe.height, probe.duration_s, probe.fps, probe.size_bytes)
    )
    if why is not None:  # the real file, not the provider's claim
        reject = _Reject(ClipStatus.REJECTED_QUALITY, why)
        await mark_candidate(deps, user_id, project_id, row, **_reject_values(reject))
        return reject
    try:
        done = await asyncio.to_thread(
            _analyse, deps, row, probe.duration_s, text_vectors[row.query]
        )
    except FfCanceled as exc:
        raise JobCanceled from exc
    except FfTimeout:
        return None
    except FfError:
        done = _Reject(ClipStatus.REJECTED_QUALITY, RejectReason.FFPROBE_FAILED)
    if isinstance(done, _Reject):
        await mark_candidate(deps, user_id, project_id, row, **_reject_values(done))
        return done
    await asyncio.to_thread(_store_embeddings, deps, row, done.embeddings)
    await mark_candidate(
        deps,
        user_id,
        project_id,
        row,
        status=ClipStatus.RANKED.value,
        reject_reason=None,
        score=done.score,
        frame_scores={"query": row.query, "scores": [round(s, 6) for s in done.scores]},
        window_start_s=Decimal(str(done.window.start_s)),
        mezz_frames=done.window.frames,
    )
    return RankedClip(
        row.provider, row.provider_id, row.query, done.score, done.window, done.mean_embedding
    )


def _embed_queries(deps: FootageDeps, queries: list[str]) -> dict[str, list[float]]:
    with deps.heavy.hold(FOOTAGE_WAIT_S):
        vectors = deps.ranker.embed_text(queries)
    return dict(zip(queries, vectors, strict=True))


async def vet_and_rank(
    deps: FootageDeps, *, user_id: UUID, project_id: UUID, candidates: Sequence[ClipCandidate]
) -> VetResult:
    """Download, probe, reject, cut-check, sample, blur-check, embed and score every candidate.

    Idempotent per `(project, provider, provider_id)`: a rejected candidate stays rejected, a ranked
    one is read back, a half-done one resumes. The result is the reproducible ranking."""
    done = [c for c in candidates if c.status in {s.value for s in DONE_STATUSES}]
    todo = [
        c
        for c in candidates
        if c.status not in {s.value for s in DONE_STATUSES | REJECTED_STATUSES}
    ]
    text_vectors: dict[str, list[float]] = {}
    if todo:
        queries = sorted({c.query for c in todo})
        text_vectors = await asyncio.to_thread(_embed_queries, deps, queries)
    gate = asyncio.Semaphore(max(1, deps.fetch_concurrency))

    async def guarded(row: ClipCandidate) -> RankedClip | _Reject | None:
        async with gate:
            try:
                return await _vet_one(deps, user_id, project_id, row, text_vectors)
            except DownloadRefused as exc:  # a transient network failure: try again next run
                log.warning("footage.download_skipped", reason=exc.reason)
                return None

    outcomes = await asyncio.gather(*(guarded(r) for r in todo))
    ranked = [o for o in outcomes if isinstance(o, RankedClip)]
    ranked += [_stored_ranked(deps, r) for r in done]
    rejected: dict[str, int] = {}
    for outcome in outcomes:
        if isinstance(outcome, _Reject):
            rejected[outcome.reason.value] = rejected.get(outcome.reason.value, 0) + 1
    skipped = sum(1 for o in outcomes if o is None)  # transient: left for the next run
    ordered = rank(ranked, seed=deps.seed)
    log.info("footage.vet", ranked=len(ordered), rejected=sum(rejected.values()), skipped=skipped)
    return VetResult(ordered, rejected, skipped, near_duplicates(ordered))


# --- wiring: what the draft job hands in (plan 006 calls these) ---------------------


async def effective_pixabay(ctx: WorkerContext, user_id: UUID) -> bool:
    """Read at job time from Postgres (ARCH §7 #25): the owner's switch, else the env default."""
    async with ctx.sessionmaker() as session:
        user = await UserRepository(session).get(user_id=user_id)
    stock = (user.settings if user is not None else {}).get("stock", {})
    return bool(stock.get("pixabay_enabled", ctx.settings.pixabay_enabled))


def build_providers(
    settings: Settings, redis: Redis, *, pixabay_on: bool
) -> tuple[StockProvider, ...]:
    """Fake clips under FAKE_STOCK, else Pexels (when a key exists) and Pixabay (only when its
    switch is on AND a key exists: otherwise it is not even constructed)."""
    if settings.fake_stock:
        if not settings.fake_stock_dir:
            msg = "FAKE_STOCK needs FAKE_STOCK_DIR (a directory made by `make fake-stock`)"
            raise ValueError(msg)
        return (FakeStockProvider(settings.fake_stock_dir),)
    pexels_key = settings.pexels_api_key.get_secret_value() if settings.pexels_api_key else None
    pixabay_key = (
        settings.pixabay_api_key.get_secret_value()
        if pixabay_on and settings.pixabay_api_key
        else None
    )
    http = httpx.Client(timeout=httpx.Timeout(20.0, connect=10.0))
    downloader = Downloader(allowed_hosts(settings.stock_host_allowlist, pixabay=bool(pixabay_key)))
    providers: list[StockProvider] = []
    if pexels_key:
        limiter = FixedWindowLimiter(redis, "pexels", settings.pexels_rate_per_hour, 3600)
        providers.append(
            PexelsProvider(
                ProviderHttp(http, "pexels", limiter, CircuitBreaker()),
                pexels_key,
                SearchCache(redis, "pexels"),
                downloader,
            )
        )
    if pixabay_key:
        limiter = FixedWindowLimiter(redis, "pixabay", settings.pixabay_rate_per_min, 60)
        providers.append(
            PixabayProvider(
                ProviderHttp(http, "pixabay", limiter, CircuitBreaker()),
                pixabay_key,
                SearchCache(redis, "pixabay"),
                downloader,
            )
        )
    if not providers:
        raise StockUnavailable("no stock provider is configured", {"reason": "no_provider"})
    return tuple(providers)


_RANKERS: dict[tuple[bool, str], ImageTextRanker] = {}


def get_ranker(settings: Settings) -> ImageTextRanker:
    """One ranker per process, built on first use (not at import); weights verified first."""
    key = (settings.fake_ml, settings.siglip_model)
    if key not in _RANKERS:
        if settings.fake_ml:
            _RANKERS[key] = FakeRanker()
        else:
            directory = verified_group(settings.models_dir, SIGLIP_GROUP)  # ModelIntegrityError
            _RANKERS[key] = SigLipRanker(directory, effective(settings, host_facts()).torch_threads)
    return _RANKERS[key]


def build_footage_deps(
    ctx: WorkerContext,
    redis: Redis,
    *,
    pixabay_on: bool,
    cancel: Callable[[], bool] | None = None,
    seed: int | str = 0,
) -> FootageDeps:
    tuning = effective(ctx.settings, host_facts())
    return FootageDeps(
        ctx,
        build_providers(ctx.settings, redis, pixabay_on=pixabay_on),
        get_ranker(ctx.settings),
        HeavyLock(redis, tuning.heavy, ctx.settings.heavy_ttl_s),
        cancel,
        tuning.fetch_concurrency,
        seed,
    )

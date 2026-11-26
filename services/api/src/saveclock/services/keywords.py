"""Where the search keywords come from (T-2.5, T-2.17).

Order (DECISIONS §8f): explicit keywords, then the model only when one is wired and allowed, then
the offline table. The model is armored: a cache, a per-day call cap, a kill-switch, a closed output
schema, one repair retry for invalid JSON only, a cost estimate and a monthly alarm. Every failure
ends in the table; nothing here raises to the caller. Only the analysis summary is ever sent.
"""

import hashlib
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError
from redis import Redis

from saveclock.adapters.llm import LlmClient, LlmError, LlmReply
from saveclock.config import Settings
from saveclock.domain.keywords import (
    KEYWORD_RE,
    MAX_KEYWORDS,
    AnalysisSummary,
    KeywordSource,
    clean_keywords,
)
from saveclock.domain.keywords_fallback import table_keywords
from saveclock.domain.prompts_keywords_v1 import (
    PROMPT_VERSION,
    SYSTEM,
    build_user_message,
    canonical_summary_json,
)

log = structlog.get_logger()

CACHE_TTL_S = 24 * 3600
CALLS_TTL_S = 48 * 3600
COST_TTL_S = 40 * 24 * 3600
KILL_KEY = "llm:kill"
# unverified: copy from the Anthropic pricing page; used only for the cost cap and the log.
# shortcut: a None price disables the per-video cost cap (the call cap and the kill-switch still
# work); upgrade when the owner fills in (input, output) USD per million tokens for the model.
LLM_PRICES: tuple[float, float] | None = None

Keyword = Annotated[str, StringConstraints(pattern=KEYWORD_RE.pattern)]


class KeywordSet(BaseModel):
    """The only accepted shape of a model reply (SEC-042): a closed object, at most 8 keywords."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    keywords: list[Keyword] = Field(min_length=1, max_length=MAX_KEYWORDS)


@dataclass(frozen=True)
class KeywordResult:
    keywords: list[str]
    source: KeywordSource
    degraded: bool = False
    cost_usd: float = 0.0


@dataclass(frozen=True)
class KeywordDeps:
    settings: Settings
    redis: Redis
    llm: LlmClient | None = None  # None: no key, the switch is off or nothing is wired
    prices: tuple[float, float] | None = field(default_factory=lambda: LLM_PRICES)
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))


def _cost(deps: KeywordDeps, reply: LlmReply) -> float | None:
    if deps.prices is None:
        return None
    return (reply.input_tokens * deps.prices[0] + reply.output_tokens * deps.prices[1]) / 1e6


def _record_cost(deps: KeywordDeps, cost: float) -> None:
    month = deps.now().strftime("%Y-%m")
    key = f"llm:cost:{month}"
    total = float(deps.redis.incrbyfloat(key, cost))
    deps.redis.expire(key, COST_TTL_S)
    budget = deps.settings.llm_monthly_budget_usd
    if (
        budget is not None
        and total > budget
        and deps.redis.set(f"llm:alarm:{month}", 1, nx=True, ex=COST_TTL_S)
    ):
        log.warning("llm.budget_alarm", month=month, total_usd=round(total, 4), budget_usd=budget)


def _within_daily_cap(deps: KeywordDeps) -> bool:
    cap = deps.settings.llm_daily_call_cap
    if cap is None:
        return True
    key = f"llm:calls:{deps.now().strftime('%Y-%m-%d')}"
    calls = int(deps.redis.incr(key))
    deps.redis.expire(key, CALLS_TTL_S)
    return calls <= cap


def _parse(text: str) -> tuple[list[str] | None, list[str]]:
    """(keywords, error types). The error types never contain model output."""
    try:
        return list(KeywordSet.model_validate_json(text).keywords), []
    except ValidationError as exc:
        return None, sorted({str(e["type"]) for e in exc.errors()})


def _call(deps: KeywordDeps, llm: LlmClient, user: str, repair: list[str] | None) -> LlmReply:
    message = user
    if repair:
        message += (
            "\n\nYour previous reply was rejected by the validator "
            f"({', '.join(repair)}). Reply with only the JSON object."
        )
    s = deps.settings
    started = time.monotonic()
    reply = llm.complete(
        SYSTEM, message, max_tokens=s.llm_max_tokens, timeout_s=float(s.llm_timeout_s)
    )
    log.info(  # counts and latency only: never a prompt or an output (SEC-045)
        "llm.call",
        model=s.llm_model,
        input_tokens=reply.input_tokens,
        output_tokens=reply.output_tokens,
        latency_ms=int((time.monotonic() - started) * 1000),
        repair=bool(repair),
    )
    return reply


def _ask_model(
    deps: KeywordDeps, llm: LlmClient, summary: AnalysisSummary
) -> tuple[list[str], float]:
    """Keywords and the estimated cost; raises LlmError or ValueError when nothing usable came."""
    user = build_user_message(summary)
    spent = 0.0
    repair: list[str] | None = None
    for attempt in range(2):
        reply = _call(deps, llm, user, repair)
        cost = _cost(deps, reply)
        if cost is None:
            log.warning("llm.prices_unset", note="cost cap and monthly alarm are inactive")
        else:
            spent += cost
            _record_cost(deps, cost)
        keywords, errors = _parse(reply.text)
        if keywords is not None:
            return keywords, spent
        cap = deps.settings.llm_cost_cap_usd_per_video
        if attempt == 1 or (cap is not None and spent >= cap):
            break
        repair = errors
    msg = "model reply failed validation"
    raise ValueError(msg)


def _table(summary: AnalysisSummary, *, degraded: bool) -> KeywordResult:
    row = table_keywords(summary.energy_bucket, summary.tempo_bucket, summary.style)
    return KeywordResult(list(row), KeywordSource.TABLE, degraded)


def resolve_keywords(
    deps: KeywordDeps, summary: AnalysisSummary, options: Mapping[str, Any]
) -> KeywordResult:
    override = clean_keywords(options.get("keywords_override") or [])
    if override:  # no network, no Redis
        return KeywordResult(override, KeywordSource.EXPLICIT)
    if deps.llm is None or deps.settings.llm_enabled is False or deps.redis.exists(KILL_KEY):
        return _table(summary, degraded=False)  # the model is intentionally off
    cache_key = (
        "kw:"
        + hashlib.sha256((PROMPT_VERSION + canonical_summary_json(summary)).encode()).hexdigest()
    )
    cached = deps.redis.get(cache_key)
    if cached is not None:
        hit = clean_keywords(json.loads(cached))
        if hit:
            return KeywordResult(hit, KeywordSource.LLM)
    if not _within_daily_cap(deps):
        log.warning("llm.daily_cap_reached")
        return _table(summary, degraded=True)
    try:
        keywords, cost = _ask_model(deps, deps.llm, summary)
    except (LlmError, ValueError) as exc:
        log.warning("llm.fallback", reason=type(exc).__name__)
        return _table(summary, degraded=True)
    deps.redis.set(cache_key, json.dumps(keywords), ex=CACHE_TTL_S)
    return KeywordResult(keywords, KeywordSource.LLM, False, cost)

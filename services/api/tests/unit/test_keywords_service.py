from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import pytest
from structlog.testing import capture_logs

from saveclock.adapters.llm import (
    FakeLlm,
    HashLlm,
    LlmError,
    LlmRateLimited,
    LlmRefusal,
    LlmReply,
    LlmTimeout,
)
from saveclock.config import Settings
from saveclock.domain.keywords import KeywordSource, summary_from_analysis
from saveclock.domain.keywords_fallback import table_keywords
from saveclock.services.keywords import KILL_KEY, KeywordDeps, resolve_keywords
from tests.conftest import ENV
from tests.factories.memory_redis import MemoryRedis

if TYPE_CHECKING:
    from redis import Redis

SUMMARY = summary_from_analysis(128.0, [0.8], [("peak", 20.0)], vibe="neon")
TABLE_ROW = list(table_keywords("high", "fast"))
GOOD = LlmReply('{"keywords": ["neon city", "rain street", "dance floor"]}', 120, 30)
BAD = LlmReply("here are some keywords: neon", 120, 10)
FIXED_NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)


def settings(**kw: Any) -> Settings:
    return Settings(_env_file=None, **{**ENV, **kw})


def deps(llm: Any = None, redis: MemoryRedis | None = None, **kw: Any) -> KeywordDeps:
    prices = kw.pop("prices", None)
    return KeywordDeps(
        settings(**kw),
        cast("Redis", redis or MemoryRedis()),
        llm,
        prices=prices,
        now=lambda: FIXED_NOW,
    )


def test_explicit_beats_an_active_llm_and_touches_neither_redis_nor_the_model() -> None:
    llm, redis = FakeLlm([GOOD]), MemoryRedis()
    res = resolve_keywords(
        deps(llm, redis, anthropic_api_key="k"), SUMMARY, {"keywords_override": ["Neon City", "x"]}
    )
    assert (res.keywords, res.source, res.degraded) == (
        ["neon city"],
        KeywordSource.EXPLICIT,
        False,
    )
    assert redis.commands == []
    assert llm.calls == []


def test_an_invalid_override_falls_through_to_the_model() -> None:
    llm = FakeLlm([GOOD])
    res = resolve_keywords(deps(llm), SUMMARY, {"keywords_override": ["a", "!!"]})
    assert res.source == KeywordSource.LLM


def test_active_llm_beats_the_table_and_the_call_is_armored() -> None:
    llm = FakeLlm([GOOD])
    with capture_logs() as logs:
        res = resolve_keywords(deps(llm), SUMMARY, {})
    assert res.source == KeywordSource.LLM
    assert res.keywords == ["neon city", "rain street", "dance floor"]
    assert llm.calls[0]["max_tokens"] == 300
    assert llm.calls[0]["timeout_s"] == 8
    assert "<analysis>" in llm.calls[0]["user"]
    text = repr(logs)
    assert "llm.call" in text
    assert "neon city" not in text  # no output in the logs
    assert "tempo_bucket" not in text  # no prompt in the logs


def test_no_model_wired_means_the_table_without_degradation() -> None:
    res = resolve_keywords(deps(None), SUMMARY, {})
    assert (res.keywords, res.source, res.degraded) == (TABLE_ROW, KeywordSource.TABLE, False)


def test_switch_off_and_kill_switch_use_the_table_without_a_call() -> None:
    llm = FakeLlm([GOOD])
    assert resolve_keywords(deps(llm, llm_enabled=False), SUMMARY, {}).source == KeywordSource.TABLE
    redis = MemoryRedis()
    redis.data[KILL_KEY] = "1"
    res = resolve_keywords(deps(llm, redis), SUMMARY, {})
    assert (res.source, res.degraded) == (KeywordSource.TABLE, False)
    assert llm.calls == []


def test_invalid_json_then_valid_makes_one_repair_call_that_never_echoes_the_output() -> None:
    llm = FakeLlm([BAD, GOOD])
    res = resolve_keywords(deps(llm), SUMMARY, {})
    assert res.source == KeywordSource.LLM
    assert len(llm.calls) == 2
    assert "rejected by the validator" in llm.calls[1]["user"]
    assert "here are some keywords" not in llm.calls[1]["user"]


def test_invalid_twice_gives_the_table_degraded_after_exactly_two_calls() -> None:
    llm = FakeLlm([BAD, BAD, GOOD])
    res = resolve_keywords(deps(llm), SUMMARY, {})
    assert (res.source, res.degraded) == (KeywordSource.TABLE, True)
    assert len(llm.calls) == 2


@pytest.mark.parametrize("error", [LlmTimeout(), LlmRefusal(), LlmRateLimited(), LlmError("x")])
def test_timeout_refusal_429_and_other_errors_fall_back_degraded_without_retry(
    error: Exception,
) -> None:
    llm = FakeLlm([error, GOOD])
    res = resolve_keywords(deps(llm), SUMMARY, {})
    assert (res.keywords, res.source, res.degraded) == (TABLE_ROW, KeywordSource.TABLE, True)
    assert len(llm.calls) == 1


def test_daily_cap_reached_gives_the_table_degraded() -> None:
    llm = FakeLlm([GOOD, GOOD])
    d = deps(llm, llm_daily_call_cap=1)
    assert resolve_keywords(d, SUMMARY, {}).source == KeywordSource.LLM
    other = replace(SUMMARY, style="rock")  # a different summary: no cache hit
    res = resolve_keywords(d, other, {})
    assert (res.source, res.degraded) == (KeywordSource.TABLE, True)
    assert len(llm.calls) == 1


def test_cache_hit_makes_no_call_and_no_cap_count() -> None:
    llm, redis = FakeLlm([GOOD]), MemoryRedis()
    d = deps(llm, redis, llm_daily_call_cap=5)
    first = resolve_keywords(d, SUMMARY, {})
    second = resolve_keywords(d, SUMMARY, {})
    assert second.keywords == first.keywords
    assert second.source == KeywordSource.LLM
    assert len(llm.calls) == 1
    assert redis.data["llm:calls:2026-11-26"] == 1
    assert all(ttl > 0 for ttl in redis.ttls.values())


def test_cost_is_recorded_per_month_and_the_alarm_logs_once() -> None:
    llm = FakeLlm([GOOD, GOOD, GOOD])
    redis = MemoryRedis()
    d = deps(llm, redis, prices=(1000.0, 1000.0), llm_monthly_budget_usd=0.1)
    with capture_logs() as logs:
        for style in ("a", "b", "c"):
            resolve_keywords(d, replace(SUMMARY, style=style), {})
    alarms = [entry for entry in logs if entry["event"] == "llm.budget_alarm"]
    assert len(alarms) == 1
    assert redis.data["llm:cost:2026-11"] == pytest.approx(3 * (120 + 30) * 1000 / 1e6)
    assert redis.ttls["llm:cost:2026-11"] > 0


def test_per_video_cost_cap_stops_the_repair_call() -> None:
    llm = FakeLlm([BAD, GOOD])
    d = deps(llm, prices=(1000.0, 1000.0), llm_cost_cap_usd_per_video=0.01)
    res = resolve_keywords(d, SUMMARY, {})
    assert (res.source, res.degraded) == (KeywordSource.TABLE, True)
    assert len(llm.calls) == 1


def test_unset_prices_warn_and_leave_the_cost_cap_inactive() -> None:
    llm = FakeLlm([BAD, GOOD])
    with capture_logs() as logs:
        res = resolve_keywords(deps(llm, llm_cost_cap_usd_per_video=0.0001), SUMMARY, {})
    assert res.source == KeywordSource.LLM
    assert res.cost_usd == 0.0
    assert any(entry["event"] == "llm.prices_unset" for entry in logs)


def test_the_cost_of_a_successful_call_is_returned() -> None:
    res = resolve_keywords(deps(FakeLlm([GOOD]), prices=(2.0, 10.0)), SUMMARY, {})
    assert res.cost_usd == pytest.approx((120 * 2.0 + 30 * 10.0) / 1e6)


def test_hash_llm_is_deterministic_and_valid() -> None:
    a = resolve_keywords(deps(HashLlm()), SUMMARY, {})
    b = resolve_keywords(deps(HashLlm()), SUMMARY, {})
    assert a.source == KeywordSource.LLM
    assert a.keywords == b.keywords
    assert len(a.keywords) == 6

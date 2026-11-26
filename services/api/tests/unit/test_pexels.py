import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import httpx
import pytest
import respx
from structlog.testing import capture_logs

from saveclock.adapters.stock.limits import (
    CircuitBreaker,
    FixedWindowLimiter,
    ProviderHttp,
    SearchCache,
)
from saveclock.adapters.stock.pexels import SEARCH_URL, PexelsProvider, parse_videos
from saveclock.adapters.stock.pixabay import SEARCH_URL as PIXABAY_URL
from saveclock.adapters.stock.pixabay import PixabayProvider, parse_hits
from saveclock.errors import StockUnavailable
from tests.factories.memory_redis import MemoryRedis

if TYPE_CHECKING:
    from redis import Redis

    pass

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
KEY = "-".join(["pexels", "fake", "k1", "z9"])  # built from pieces: a test value, not a secret
PIXABAY_KEY = "-".join(["pixabay", "fake", "k2", "y8"])  # built from pieces: a test value


class AlwaysOk:
    """A limiter that never blocks (the real one is covered in test_stock_limits)."""

    def acquire(self, wait_max_s: float = 20.0) -> bool:
        return True


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class Recorder:
    def __init__(self) -> None:
        self.sleeps: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.sleeps.append(seconds)


class Fixed:
    """A cache backed by MemoryRedis with real get/set semantics for JSON strings."""

    def __init__(self) -> None:
        self.redis = MemoryRedis()


def build(
    breaker: CircuitBreaker | None = None, sleeps: Recorder | None = None
) -> tuple[PexelsProvider, Recorder, CircuitBreaker, MemoryRedis]:
    sleeps = sleeps or Recorder()
    breaker = breaker or CircuitBreaker()
    redis = MemoryRedis()
    http = ProviderHttp(
        httpx.Client(),
        "pexels",
        cast("FixedWindowLimiter", AlwaysOk()),
        breaker,
        sleep=sleeps,
    )
    provider = PexelsProvider(http, KEY, SearchCache(cast("Redis", redis), "pexels"))
    return provider, sleeps, breaker, redis


def pexels_json() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / "pexels_search.json").read_text())
    return data


def test_the_fixture_is_marked_hand_written() -> None:
    assert "HAND-WRITTEN" in pexels_json()["_note"]


def test_parsing_picks_the_portrait_file_closest_to_1080_and_skips_the_rest() -> None:
    clips = parse_videos(pexels_json())
    by_id = {c.provider_id: c for c in clips}
    assert set(by_id) == {"3001", "3004"}  # landscape 3002 and no-720p 3003 are skipped
    good = by_id["3001"]
    assert (good.width, good.height) == (1080, 1920)  # not the 4K and not the webm
    assert good.file_url.endswith("3001-hd_1080_1920_25fps.mp4")
    assert good.license == "Pexels License"
    assert (good.author, good.fps, good.duration_s) == ("Ada Example", 25.0, 14.0)
    assert good.page_url == "https://www.pexels.com/video/neon-city-street-3001/"
    mid = by_id["3004"]
    assert mid.width == 900  # nothing >= 1080: the largest >= 720
    assert mid.fps is None


@pytest.mark.respx(assert_all_mocked=True)
def test_search_sends_the_key_only_in_the_authorization_header(
    respx_mock: respx.MockRouter,
) -> None:
    route = respx_mock.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=pexels_json()))
    provider, _, _, _ = build()
    with capture_logs() as logs:
        clips = provider.search("neon city", per_page=40)
    request = route.calls.last.request
    assert request.headers["authorization"] == KEY
    assert KEY not in str(request.url)
    assert dict(request.url.params) == {
        "query": "neon city",
        "orientation": "portrait",
        "size": "medium",
        "per_page": "40",
        "page": "1",
    }
    assert len(clips) == 2
    assert KEY not in repr(logs)
    assert "neon city" not in repr(logs)  # host, path, status and latency only
    assert any(e["event"] == "stock.http" and e["status"] == 200 for e in logs)


@pytest.mark.respx(assert_all_mocked=True)
def test_429_then_200_retries_honouring_retry_after(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(SEARCH_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(200, json=pexels_json()),
        ]
    )
    provider, sleeps, _, _ = build()
    assert len(provider.search("neon city")) == 2
    assert sleeps.sleeps == [7.0]


@pytest.mark.respx(assert_all_mocked=True)
def test_three_500s_then_unavailable_with_the_backoff_table(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(SEARCH_URL).mock(return_value=httpx.Response(500))
    provider, sleeps, _, _ = build()
    with pytest.raises(StockUnavailable) as info:
        provider.search("neon city")
    assert route.call_count == 4  # the first try plus three retries
    assert sleeps.sleeps == [2.0, 4.0, 8.0]
    assert info.value.details == {"reason": "upstream"}


@pytest.mark.respx(assert_all_mocked=True)
@pytest.mark.parametrize("status", [401, 403])
def test_a_rejected_key_is_not_retried(respx_mock: respx.MockRouter, status: int) -> None:
    route = respx_mock.get(SEARCH_URL).mock(return_value=httpx.Response(status))
    provider, sleeps, _, _ = build()
    with pytest.raises(StockUnavailable) as info:
        provider.search("neon city")
    assert route.call_count == 1
    assert sleeps.sleeps == []
    assert info.value.details == {"reason": "key_rejected"}
    assert KEY not in str(info.value)


@pytest.mark.respx(assert_all_mocked=True)
def test_other_4xx_a_network_error_and_a_bad_body(respx_mock: respx.MockRouter) -> None:
    provider, sleeps, _, _ = build()
    respx_mock.get(SEARCH_URL).mock(return_value=httpx.Response(404))
    with pytest.raises(StockUnavailable) as bad_status:
        provider.search("a")
    assert bad_status.value.details == {"reason": "bad_status"}
    respx_mock.get(SEARCH_URL).mock(return_value=httpx.Response(200, text="<html>"))
    with pytest.raises(StockUnavailable) as bad_body:
        provider.search("b")
    assert bad_body.value.details == {"reason": "bad_body"}
    respx_mock.get(SEARCH_URL).mock(
        side_effect=[httpx.ConnectError("boom " + KEY), httpx.Response(200, json=pexels_json())]
    )
    assert len(provider.search("c")) == 2
    assert sleeps.sleeps == [2.0]


@pytest.mark.respx(assert_all_mocked=True)
def test_circuit_breaker_opens_after_five_failures_and_half_opens_after_sixty_seconds(
    respx_mock: respx.MockRouter,
) -> None:
    clock = Clock()
    breaker = CircuitBreaker(clock=clock)
    route = respx_mock.get(SEARCH_URL).mock(return_value=httpx.Response(500))
    provider, _, _, _ = build(breaker)
    with pytest.raises(StockUnavailable):
        provider.search("a")  # 4 failures
    assert breaker.allow()
    with pytest.raises(StockUnavailable):
        provider.search("b")  # the fifth failure opens it
    calls = route.call_count
    with pytest.raises(StockUnavailable) as open_info:
        provider.search("c")
    assert open_info.value.details == {"reason": "circuit_open"}
    assert route.call_count == calls  # no request while open
    clock.now = 59.0
    assert not breaker.allow()
    clock.now = 61.0
    route.mock(return_value=httpx.Response(200, json=pexels_json()))
    assert len(provider.search("d")) == 2  # the half-open trial succeeds and closes it
    assert breaker.allow()


def test_breaker_half_open_failure_reopens_and_old_failures_expire() -> None:
    clock = Clock()
    b = CircuitBreaker(clock=clock)
    for _ in range(4):
        b.record_failure()
    clock.now = 31.0
    b.record_failure()  # the four earlier ones are out of the 30 s window
    assert b.allow()
    for _ in range(4):
        b.record_failure()
    assert not b.allow()
    clock.now = 100.0
    assert b.allow()  # the single trial
    assert not b.allow()  # a second caller during the trial is refused
    b.record_failure()
    assert not b.allow()


@pytest.mark.respx(assert_all_mocked=True)
def test_the_cache_serves_the_second_identical_query_without_http(
    respx_mock: respx.MockRouter,
) -> None:
    route = respx_mock.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=pexels_json()))
    provider, _, _, redis = build()
    first = provider.search("neon city")
    second = provider.search("neon city")
    assert second == first
    assert route.call_count == 1
    assert all(ttl == 24 * 3600 for ttl in redis.ttls.values())
    provider.search("other")
    assert route.call_count == 2


def test_rate_limit_wait_exceeded_is_stock_unavailable() -> None:
    class Never:
        def acquire(self, wait_max_s: float = 20.0) -> bool:
            return False

    http = ProviderHttp(
        httpx.Client(), "pexels", cast("FixedWindowLimiter", Never()), CircuitBreaker()
    )
    with pytest.raises(StockUnavailable) as info:
        PexelsProvider(http, KEY, SearchCache(cast("Redis", MemoryRedis()), "pexels")).search("x")
    assert info.value.details == {"reason": "rate_limited"}


# --- Pixabay: the key travels in the query string and must never be logged -----------------------


def pixabay_json() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / "pixabay_search.json").read_text())
    return data


def test_pixabay_parsing_picks_a_portrait_rendition() -> None:
    clips = parse_hits(pixabay_json())
    assert [c.provider_id for c in clips] == ["4101"]
    c = clips[0]
    assert (c.width, c.height, c.provider, c.license) == (
        1080,
        1920,
        "pixabay",
        "Pixabay Content License",
    )
    assert c.file_url.endswith("4101_medium.mp4")
    assert c.file_size == 4_000_000
    assert c.author_url == "https://pixabay.com/users/Example-Footage-555/"


@pytest.mark.respx(assert_all_mocked=True)
def test_pixabay_never_logs_the_key_or_the_url(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(PIXABAY_URL).mock(return_value=httpx.Response(200, json=pixabay_json()))
    http = ProviderHttp(
        httpx.Client(), "pixabay", cast("FixedWindowLimiter", AlwaysOk()), CircuitBreaker()
    )
    redis = MemoryRedis()
    provider = PixabayProvider(http, PIXABAY_KEY, SearchCache(cast("Redis", redis), "pixabay"))
    with capture_logs() as logs:
        clips = provider.search("neon city")
    assert len(clips) == 1
    assert route.calls.last.request.url.params["key"] == PIXABAY_KEY
    assert PIXABAY_KEY not in repr(logs)
    assert PIXABAY_KEY not in repr(redis.data)  # not part of the cache key or the cached rows
    provider.search("neon city")
    assert route.call_count == 1


@pytest.mark.respx(assert_all_mocked=True)
def test_a_pixabay_failure_does_not_put_the_key_in_the_error(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(PIXABAY_URL).mock(side_effect=httpx.ConnectError("failed " + PIXABAY_KEY))
    http = ProviderHttp(
        httpx.Client(),
        "pixabay",
        cast("FixedWindowLimiter", AlwaysOk()),
        CircuitBreaker(),
        sleep=Recorder(),
    )
    provider = PixabayProvider(
        http, PIXABAY_KEY, SearchCache(cast("Redis", MemoryRedis()), "pixabay")
    )
    with capture_logs() as logs, pytest.raises(StockUnavailable) as info:
        provider.search("neon city")
    assert PIXABAY_KEY not in str(info.value)
    assert PIXABAY_KEY not in repr(logs)
    assert info.value.__cause__ is None


def test_both_providers_download_through_the_shared_downloader(tmp_path: Path) -> None:
    from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
    from saveclock.adapters.stock.download import Downloader

    calls: list[tuple[str, int]] = []

    class Spy(Downloader):
        def fetch(self, clip: Any, blobs: Any, key: str, *, max_bytes: int, cancel: Any) -> int:
            calls.append((clip.provider_id, max_bytes))
            return 7

    store = FilesystemBlobStore(tmp_path, 0)
    limiter = cast("FixedWindowLimiter", AlwaysOk())
    http = ProviderHttp(httpx.Client(), "x", limiter, CircuitBreaker())
    clip = parse_videos(pexels_json())[0]
    pexels = PexelsProvider(http, KEY, SearchCache(cast("Redis", MemoryRedis()), "p"), Spy())
    pixabay = PixabayProvider(
        http, PIXABAY_KEY, SearchCache(cast("Redis", MemoryRedis()), "q"), Spy()
    )
    assert pexels.download(clip, store, "work/x/a.mp4", max_bytes=5, cancel=None) == 7
    assert pixabay.download(clip, store, "work/x/b.mp4", max_bytes=6, cancel=None) == 7
    assert calls == [("3001", 5), ("3001", 6)]

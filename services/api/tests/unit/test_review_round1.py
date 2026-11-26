"""Review round 1: log hygiene, bounded cuts, slow-drip downloads, breaker trial, bad bodies."""

import logging
import time
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import httpx
import pytest

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.safe_http import DownloadRefused, safe_download
from saveclock.adapters.scenedetect import DetectionStopped, detect_cuts
from saveclock.adapters.stock.limits import (
    CircuitBreaker,
    FixedWindowLimiter,
    ProviderHttp,
    SearchCache,
)
from saveclock.adapters.stock.pexels import SEARCH_URL as PEXELS_URL
from saveclock.adapters.stock.pexels import PexelsProvider
from saveclock.adapters.stock.pixabay import PixabayProvider
from saveclock.errors import StockUnavailable
from saveclock.observability.logging import QUIET_LOGGERS, configure_logging
from tests.factories.memory_redis import MemoryRedis
from tests.factories.stock import fake_stock
from tests.unit.test_pexels import AlwaysOk, Clock, pixabay_json

if TYPE_CHECKING:
    from redis import Redis

PIXABAY_KEY = "-".join(["pixabay", "fake", "k3", "x7"])


@pytest.fixture
def quiet_loggers_restored() -> Iterator[None]:
    yield
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.NOTSET)


def test_a_pixabay_search_leaves_the_key_out_of_every_log_record(
    caplog: pytest.LogCaptureFixture, quiet_loggers_restored: None
) -> None:
    """httpx logs `HTTP Request: GET <url>` at INFO, and Pixabay's key is in the URL."""
    configure_logging(level="INFO", env="ci", version="t")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=pixabay_json())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = ProviderHttp(client, "pixabay", cast("FixedWindowLimiter", AlwaysOk()), CircuitBreaker())
    provider = PixabayProvider(http, PIXABAY_KEY, SearchCache(cast("Redis", MemoryRedis()), "q"))
    with caplog.at_level(logging.DEBUG):
        assert len(provider.search("neon city")) == 1
    assert seen[0].url.params["key"] == PIXABAY_KEY  # the request itself carries it
    for record in caplog.records:
        assert PIXABAY_KEY not in record.getMessage()
        assert PIXABAY_KEY not in str(record.args)
    assert PIXABAY_KEY not in caplog.text


# --- bounded cut detection ----------------------------------------------------------------------


@pytest.mark.ffmpeg
def test_cut_detection_honours_a_time_limit_and_a_cancel(ffmpeg_tools: Any, tmp_path: Path) -> None:
    path = fake_stock.make_clip(ffmpeg_tools, fake_stock.SPECS[5], tmp_path / "cuts.mp4")
    assert detect_cuts(path, cancel=lambda: False) == [2.0, 4.0, 6.0]
    with pytest.raises(DetectionStopped, match="timeout"):
        detect_cuts(path, timeout_s=-1.0, poll_s=0.001)
    with pytest.raises(DetectionStopped, match="canceled"):
        detect_cuts(path, cancel=lambda: True, poll_s=0.001)


# --- a slow-drip server trips the wall clock ----------------------------------------------------


def test_a_slow_drip_body_trips_the_wall_clock_deadline(tmp_path: Path) -> None:
    (tmp_path / "b").mkdir()
    blobs = FilesystemBlobStore(tmp_path / "b", 0)
    sent: list[httpx.Request] = []

    def drip() -> Iterator[bytes]:
        yield b"\x00\x00\x00\x18ftypisom" + b"\x00" * 16
        for _ in range(100):
            time.sleep(0.05)
            yield b"x"

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, headers={"content-type": "video/mp4"}, content=drip())

    with pytest.raises(DownloadRefused) as info:
        safe_download(
            "https://videos.pexels.com/a.mp4",
            blobs,
            "work/x/a.mp4",
            hosts={"videos.pexels.com"},
            max_bytes=1 << 20,
            resolver=lambda host, port: ["93.184.216.34"],
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            wall_clock_s=0.2,
        )
    assert info.value.reason == "timeout"
    assert sent[0].headers["accept-encoding"] == "identity"
    assert not blobs.exists("work/x/a.mp4")


# --- the half-open trial must not stay claimed after a 4xx --------------------------------------


def test_a_4xx_in_the_half_open_trial_releases_the_probe() -> None:
    clock = Clock()
    breaker = CircuitBreaker(clock=clock)
    for _ in range(5):
        breaker.record_failure()
    clock.now = 61.0
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    http = ProviderHttp(client, "p", cast("FixedWindowLimiter", AlwaysOk()), breaker)
    with pytest.raises(StockUnavailable):
        http.get_json("https://api.pexels.com/x", params={})
    assert breaker.allow()  # the next trial is allowed (not stuck half-open forever)


# --- malformed answers --------------------------------------------------------------------------


@pytest.mark.parametrize("which", ["pexels", "pixabay"])
def test_a_malformed_hit_is_stock_unavailable(which: str) -> None:
    file = {"file_type": "video/mp4", "width": 1080, "height": 1920, "link": "u"}
    body: dict[str, Any] = (  # a hit without an `id`
        {"videos": [{"width": 1080, "height": 1920, "video_files": [file]}]}
        if which == "pexels"
        else {"hits": [{"videos": {"large": {"url": "u", "width": 1080, "height": 1920}}}]}
    )
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    http = ProviderHttp(client, which, cast("FixedWindowLimiter", AlwaysOk()), CircuitBreaker())
    cache = SearchCache(cast("Redis", MemoryRedis()), which)
    provider = (
        PexelsProvider(http, "k", cache) if which == "pexels" else PixabayProvider(http, "k", cache)
    )
    with pytest.raises(StockUnavailable) as info:
        provider.search("x")
    assert info.value.details == {"reason": "bad_body"}
    assert PEXELS_URL.startswith("https://")

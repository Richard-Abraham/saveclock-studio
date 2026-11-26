"""One real round trip to Pexels (plan 005 Step 11). Never part of `make test` or `make check`.

Run it with the key in the environment (the key is read from the variable, never printed):
    PEXELS_API_KEY=... uv --directory services/api run pytest -q -m live
Without the key this file is not collected (tests/live/conftest.py prints SKIPPED).
"""

import os
from pathlib import Path

import httpx
import pytest
from redis import Redis

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.ffmpeg import Tools, probe_stock
from saveclock.adapters.stock.limits import (
    CircuitBreaker,
    FixedWindowLimiter,
    ProviderHttp,
    SearchCache,
)
from saveclock.adapters.stock.pexels import PexelsProvider
from saveclock.domain.stock_rules import MAX_DOWNLOAD_BYTES
from tests.integration.conftest import REDIS_URL

pytestmark = pytest.mark.live


def test_search_download_and_probe_one_portrait_clip(tmp_path: Path, ffmpeg_tools: Tools) -> None:
    redis: Redis = Redis.from_url(REDIS_URL)
    http = ProviderHttp(
        httpx.Client(timeout=20.0),
        "pexels",
        FixedWindowLimiter(redis, "pexels-live", 200, 3600),
        CircuitBreaker(),
    )
    provider = PexelsProvider(http, os.environ["PEXELS_API_KEY"], SearchCache(redis, "pexels-live"))
    clips = provider.search("city night", per_page=10)
    assert len(clips) >= 1
    assert all(c.width >= 720 and c.height > c.width for c in clips)
    clip = min(clips, key=lambda c: c.duration_s)
    blobs = FilesystemBlobStore(tmp_path, 0)
    written = provider.download(
        clip, blobs, "work/live/raw.mp4", max_bytes=MAX_DOWNLOAD_BYTES, cancel=None
    )
    assert written > 0
    probe = probe_stock(ffmpeg_tools, blobs.local_path("work/live/raw.mp4"))
    assert probe.width >= 720
    assert probe.height > probe.width

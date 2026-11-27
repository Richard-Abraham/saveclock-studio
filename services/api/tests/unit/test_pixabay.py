"""Pixabay `video_by_id` (plan 008, rehydration): fixtures only, no network."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import httpx
import pytest
import respx

from saveclock.adapters.stock.limits import (
    CircuitBreaker,
    FixedWindowLimiter,
    ProviderHttp,
    SearchCache,
)
from saveclock.adapters.stock.pixabay import SEARCH_URL, PixabayProvider
from tests.factories.memory_redis import MemoryRedis

if TYPE_CHECKING:
    from redis import Redis

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
KEY = "-".join(["pixabay", "fake", "k2", "y8"])  # built from pieces: a test value


class AlwaysOk:
    def acquire(self, wait_max_s: float = 20.0) -> bool:
        return True


def build() -> PixabayProvider:
    http = ProviderHttp(
        httpx.Client(),
        "pixabay",
        cast("FixedWindowLimiter", AlwaysOk()),
        CircuitBreaker(),
        sleep=lambda _s: None,
    )
    return PixabayProvider(http, KEY, SearchCache(cast("Redis", MemoryRedis()), "pixabay"))


def fixture() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / "pixabay_search.json").read_text())
    return data


@pytest.mark.respx(assert_all_mocked=True)
def test_video_by_id_asks_with_the_id_and_returns_that_clip(respx_mock: respx.MockRouter) -> None:
    hit = next(h for h in fixture()["hits"] if h["id"] == 4101)
    route = respx_mock.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"total": 1, "totalHits": 1, "hits": [hit]})
    )
    clip = build().video_by_id("4101")
    assert clip is not None
    assert (clip.provider, clip.provider_id) == ("pixabay", "4101")
    assert dict(route.calls.last.request.url.params) == {"id": "4101", "key": KEY}


@pytest.mark.respx(assert_all_mocked=True)
def test_an_empty_hits_list_or_a_404_means_gone(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(SEARCH_URL, params={"id": "1"}).mock(
        return_value=httpx.Response(200, json={"total": 0, "totalHits": 0, "hits": []})
    )
    respx_mock.get(SEARCH_URL, params={"id": "2"}).mock(return_value=httpx.Response(404))
    provider = build()
    assert provider.video_by_id("1") is None
    assert provider.video_by_id("2") is None


@pytest.mark.respx(assert_all_mocked=True)
def test_a_hit_with_another_id_is_not_the_clip(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=fixture()))
    assert build().video_by_id("999999") is None

"""search(): provider -> prefilter -> candidate rows, with a real database and the fake provider."""

from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import pytest

from saveclock.adapters.blobstore.port import BlobStore
from saveclock.adapters.stock.fake import FakeStockProvider
from saveclock.adapters.stock.port import StockClip, StockProvider
from saveclock.config import Settings
from saveclock.errors import StockUnavailable
from saveclock.services.footage import build_providers, effective_pixabay
from saveclock.services.footage import search as search_service
from tests.conftest import ENV
from tests.integration.footage_harness import OWNER, Footage

if TYPE_CHECKING:
    from redis import Redis

pytestmark = pytest.mark.integration


class Scripted:
    """A provider that answers from a function; counts its calls."""

    def __init__(self, name: str, answer: Callable[[str], list[StockClip]]) -> None:
        self.name, self.answer, self.queries = name, answer, []  # type: ignore[var-annotated]

    def search(self, query: str, *, page: int = 1, per_page: int = 40) -> list[StockClip]:
        self.queries.append(query)
        return self.answer(query)

    def download(
        self, clip: StockClip, blobs: BlobStore, key: str, *, max_bytes: int, cancel: object
    ) -> int:
        raise AssertionError("not used here")


def clip(i: int, provider: str = "pexels", width: int = 1080, height: int = 1920) -> StockClip:
    return StockClip(
        provider,
        f"{provider}-{i}",
        "https://p/x",
        "A",
        None,
        "L",
        width,
        height,
        10.0,
        30.0,
        f"https://v/{i}.mp4",
    )


async def test_prefilter_keeps_only_usable_clips_and_search_is_idempotent(footage: Footage) -> None:
    result = await footage.search(["neon city"])
    rows = await footage.rows()
    names = sorted(r.provider_id for r in rows)
    assert result.added == len(rows) == 7
    assert "fake-landscape" not in names  # not portrait
    assert "fake-small_portrait" not in names  # 480 wide
    assert "fake-short_portrait" not in names  # 2 s
    assert "fake-blurry_portrait" in names  # metadata looks fine; the real frames decide later
    assert {r.status for r in rows} == {"found"}
    assert {r.query for r in rows} == {"neon city"}
    assert all(r.license == "Pexels License" and r.author == "Fake Author" for r in rows)
    assert all(r.download_url and r.download_url.startswith("fake://") for r in rows)
    again = await footage.search(["neon city"])
    assert again.added == 0
    assert len(await footage.rows()) == 7


async def test_yield_and_usable_counts_per_keyword(footage: Footage) -> None:
    result = await footage.search(["neon city", "rain street"])
    assert result.usable["neon city"] >= 6  # the ladder stops here
    assert result.search_yield == 0.0  # QM-032: no keyword has 20 portrait clips at >= 1080p


async def test_the_ladder_broadens_a_keyword_with_few_usable_clips(footage: Footage) -> None:
    scripted = Scripted("pexels", lambda q: [clip(1)] if q == "night" else [])
    deps = replace(footage.deps, providers=(cast("StockProvider", scripted),))
    result = await search_service(
        deps,
        user_id=OWNER,
        project_id=footage.pid,
        keywords=["neon city night"],
        fallback=["fireworks"],
    )
    assert scripted.queries == ["neon city night", "city night", "night", "fireworks"]
    assert result.usable == {"neon city night": 1}
    (row,) = await footage.rows()
    assert row.query == "night"  # the query that found it is the one the ranker will use


async def test_pixabay_is_asked_only_when_the_first_provider_returns_too_few(
    footage: Footage,
) -> None:
    pexels = Scripted("pexels", lambda q: [clip(i) for i in range(6)])
    pixabay = Scripted("pixabay", lambda q: [clip(100, "pixabay")])
    deps = replace(
        footage.deps, providers=(cast("StockProvider", pexels), cast("StockProvider", pixabay))
    )
    await search_service(deps, user_id=OWNER, project_id=footage.pid, keywords=["a b"])
    assert pixabay.queries == []
    few = Scripted("pexels", lambda q: [clip(1)])
    deps = replace(
        footage.deps, providers=(cast("StockProvider", few), cast("StockProvider", pixabay))
    )
    await search_service(deps, user_id=OWNER, project_id=footage.pid, keywords=["a b"])
    assert pixabay.queries == ["a b", "b"]  # called after Pexels returned too few
    providers = {r.provider for r in await footage.rows()}
    assert providers == {"pexels", "pixabay"}


async def test_an_unavailable_provider_raises_only_when_nothing_was_found(footage: Footage) -> None:
    def boom(query: str) -> list[StockClip]:
        raise StockUnavailable("down", {"reason": "upstream"})

    down = Scripted("pexels", boom)
    deps = replace(footage.deps, providers=(cast("StockProvider", down),))
    with pytest.raises(StockUnavailable):
        await search_service(deps, user_id=OWNER, project_id=footage.pid, keywords=["a b"])

    def flaky(query: str) -> list[StockClip]:
        if query == "a b":
            raise StockUnavailable("down", {"reason": "upstream"})
        return [clip(1)]

    deps = replace(footage.deps, providers=(cast("StockProvider", Scripted("pexels", flaky)),))
    result = await search_service(deps, user_id=OWNER, project_id=footage.pid, keywords=["a b"])
    assert result.added == 1


async def test_a_qm032_yield_counts_keywords_with_enough_portrait_hd_clips(
    footage: Footage,
) -> None:
    many = Scripted("pexels", lambda q: [clip(i) for i in range(25)] if q == "good" else [clip(1)])
    deps = replace(footage.deps, providers=(cast("StockProvider", many),))
    result = await search_service(
        deps, user_id=OWNER, project_id=footage.pid, keywords=["good", "poor"]
    )
    assert result.search_yield == 0.5


# --- the Pixabay switch and the provider wiring (T-2.6, both states) ---------------------------


def worker_settings(**kw: object) -> Settings:
    base = {**ENV, "pexels_api_key": "pexels-key", "pixabay_api_key": "pixabay-key", **kw}
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


def test_switch_off_never_constructs_pixabay_even_with_a_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spy = MagicMock()
    monkeypatch.setattr("saveclock.services.footage.PixabayProvider", spy)
    providers = build_providers(worker_settings(), cast("Redis", MagicMock()), pixabay_on=False)
    assert [p.name for p in providers] == ["pexels"]
    spy.assert_not_called()


def test_switch_on_without_a_key_is_not_called() -> None:
    settings = worker_settings(pixabay_api_key=None)
    providers = build_providers(settings, cast("Redis", MagicMock()), pixabay_on=True)
    assert [p.name for p in providers] == ["pexels"]


def test_switch_on_with_a_key_adds_pixabay_and_its_hosts_after_pexels() -> None:
    providers = build_providers(worker_settings(), cast("Redis", MagicMock()), pixabay_on=True)
    assert [p.name for p in providers] == ["pexels", "pixabay"]


def test_no_key_and_no_fake_is_stock_unavailable_and_fake_needs_its_directory() -> None:
    with pytest.raises(StockUnavailable):
        build_providers(
            worker_settings(pexels_api_key=None), cast("Redis", MagicMock()), pixabay_on=False
        )
    with pytest.raises(ValueError, match="FAKE_STOCK_DIR"):
        build_providers(
            worker_settings(fake_stock=True), cast("Redis", MagicMock()), pixabay_on=False
        )


def test_fake_stock_uses_the_directory(fake_clips: object) -> None:
    providers = build_providers(
        worker_settings(fake_stock=True, fake_stock_dir=str(fake_clips)),
        cast("Redis", MagicMock()),
        pixabay_on=False,
    )
    assert isinstance(providers[0], FakeStockProvider)


async def test_the_effective_switch_is_read_from_the_database(footage: Footage) -> None:
    assert await effective_pixabay(footage.ctx, OWNER) is False  # the env default
    async with footage.ctx.sessionmaker() as session:
        from sqlalchemy import text

        await session.execute(
            text(
                'UPDATE users SET settings = \'{"stock": {"pixabay_enabled": true}}\' WHERE id = :i'
            ),
            {"i": OWNER},
        )
        await session.commit()
    assert await effective_pixabay(footage.ctx, OWNER) is True
    from uuid import uuid4

    assert await effective_pixabay(footage.ctx, uuid4()) is False

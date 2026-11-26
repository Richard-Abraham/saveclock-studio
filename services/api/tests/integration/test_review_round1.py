"""Review round 1: one bad candidate or a busy slot must not fail the whole stage."""

from dataclasses import replace
from typing import Any

import pytest

from saveclock.adapters.heavy_lock import HeavyLockTimeout
from saveclock.adapters.stock.fake import FakeStockProvider
from saveclock.services import footage as footage_module
from saveclock.services import normalize as normalize_module
from saveclock.services.footage import build_footage_deps
from saveclock.services.normalize import normalize_topk
from tests.integration.footage_harness import OWNER, Footage

pytestmark = [pytest.mark.integration, pytest.mark.ffmpeg]


class NoSlot:
    """A heavy lock whose slot never frees up."""

    slots = 1

    def hold(self, wait_s: float) -> Any:
        raise HeavyLockTimeout("no heavy slot free")


async def test_a_lock_that_always_times_out_skips_candidates_and_the_stage_completes(
    footage: Footage, monkeypatch: pytest.MonkeyPatch
) -> None:
    await footage.search(["red"])
    deps = replace(footage.deps, heavy=NoSlot())  # type: ignore[arg-type]
    # the text embedding takes the slot once for the whole stage: let that one through
    ranker_texts = footage.deps.ranker.embed_text(["red"])
    monkeypatch.setattr(
        footage_module, "_embed_queries", lambda d, q: dict(zip(q, ranker_texts, strict=True))
    )
    result = await footage_module.vet_and_rank(
        deps, user_id=OWNER, project_id=footage.pid, candidates=await footage.rows()
    )
    assert result.ranked == []
    assert result.skipped == 7  # every candidate waits for the next run
    assert {r.status for r in await footage.rows()} == {"downloaded"}


async def test_normalize_with_no_slot_returns_nothing_instead_of_failing(footage: Footage) -> None:
    await footage.search(["red"])
    vetted = await footage.vet()
    deps = replace(footage.deps, heavy=NoSlot())  # type: ignore[arg-type]
    done = await normalize_topk(
        deps, user_id=OWNER, project_id=footage.pid, ranked=vetted.ranked, cuts=3
    )
    assert done == []
    assert {r.status for r in await footage.rows(["ranked"])} == {"ranked"}


async def test_a_detect_cuts_failure_rejects_the_clip_once_not_stuck_downloaded(
    footage: Footage, monkeypatch: pytest.MonkeyPatch
) -> None:
    await footage.search(["red"])

    def poison(*a: object, **k: object) -> None:
        raise RuntimeError("VideoOpenFailure")

    monkeypatch.setattr(footage_module, "detect_cuts", poison)
    result = await footage.vet()
    assert result.rejected == {"ffprobe_failed": 7}
    assert {(r.status, r.reject_reason) for r in await footage.rows()} == {
        ("rejected_quality", "ffprobe_failed")
    }
    again = await footage.vet()  # rejected rows are not retried
    assert again.rejected == {}


async def test_a_redelivered_normalize_returns_the_stored_result_without_encoding(
    footage: Footage, monkeypatch: pytest.MonkeyPatch
) -> None:
    await footage.search(["red"])
    vetted = await footage.vet()
    first = await normalize_topk(
        footage.deps, user_id=OWNER, project_id=footage.pid, ranked=vetted.ranked, cuts=1
    )

    def never(*a: object, **k: object) -> None:
        raise AssertionError("encoded twice")

    monkeypatch.setattr(normalize_module, "build_mezz", never)
    second = await normalize_topk(
        footage.deps, user_id=OWNER, project_id=footage.pid, ranked=vetted.ranked, cuts=1
    )
    assert second == first
    assert len(first) == 2


async def test_the_deps_builder_hands_back_a_close_for_its_http_client(footage: Footage) -> None:
    deps = build_footage_deps(footage.ctx, footage.redis, pixabay_on=False)
    assert isinstance(deps.providers[0], FakeStockProvider)
    deps.close()  # the shared client is closed (idempotent)
    deps.close()

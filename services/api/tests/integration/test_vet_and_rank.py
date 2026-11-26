"""vet_and_rank with the real FFmpeg, the real PySceneDetect, real Postgres/Redis/blob store.
Only the embedding model is a double: FakeRanker (hash) and the hand-written ColourRanker oracle."""

import threading
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from saveclock.adapters.blobstore.blob_keys import emb_key, raw_key
from saveclock.adapters.blobstore.port import BlobStore
from saveclock.adapters.safe_http import DownloadRefused
from saveclock.adapters.siglip import FakeRanker, hash_vector
from saveclock.adapters.stock.port import StockClip, StockProvider
from saveclock.domain.sampling import cosine
from saveclock.repositories.candidates import CandidateRepository
from saveclock.services.analysis import JobCanceled
from saveclock.services.footage import vet_and_rank
from tests.integration.footage_harness import OWNER, ColourRanker, Footage

pytestmark = [pytest.mark.integration, pytest.mark.ffmpeg]


async def by_status(footage: Footage) -> dict[str, tuple[str, str | None]]:
    return {
        r.provider_id.removeprefix("fake-"): (r.status, r.reject_reason)
        for r in await footage.rows()
    }


async def test_every_rule_on_the_real_clips(footage: Footage) -> None:
    await footage.search(["red"])
    await footage.add("small_portrait", width=720, height=1280)  # claims 720 wide, is 480
    await footage.add("short_portrait")  # claims 10 s, is 2 s
    result = await footage.with_ranker(ColourRanker()).vet()
    status = await by_status(footage)
    assert status["cut_short_portrait"] == ("rejected_cut", "no_cut_free_window")
    assert status["small_portrait"] == ("rejected_quality", "too_small")
    assert status["short_portrait"] == ("rejected_quality", "too_short")
    assert status["blurry_portrait"] == ("rejected_quality", "blurry")
    for name in (
        "red_portrait",
        "green_portrait",
        "blue_portrait",
        "gradient_portrait",
        "cut_long_portrait",
    ):
        assert status[name] == ("ranked", None), name
    assert result.rejected == {
        "no_cut_free_window": 1,
        "too_small": 1,
        "too_short": 1,
        "blurry": 1,
    }
    assert len(result.ranked) == 5


async def test_a_clip_with_one_cut_keeps_the_longest_gap_as_its_window(footage: Footage) -> None:
    await footage.search(["red"])
    await footage.vet()
    row = await footage.by_id("cut_long_portrait")
    assert row.window_start_s == Decimal("0.200")  # the 4 s gap shrunk by the 0.2 s margin
    assert row.mezz_frames == 108  # 3.6 s
    plain = await footage.by_id("red_portrait")
    assert plain.window_start_s == Decimal("0.200")
    assert plain.mezz_frames == 168  # 6 s - 0.4 s = 5.6 s
    assert row.frame_scores is not None
    assert row.frame_scores["query"] == "red"
    assert len(row.frame_scores["scores"]) == 3  # one frame per second of the window


async def test_the_ranked_order_follows_the_independent_colour_oracle(footage: Footage) -> None:
    await footage.search(["red"])
    result = await footage.with_ranker(ColourRanker()).vet()
    top_two = {c.provider_id for c in result.ranked[:2]}
    assert top_two == {"fake-red_portrait", "fake-cut_long_portrait"}  # both red where we look
    assert result.ranked[0].score == pytest.approx(1.0, abs=0.01)
    assert [c.score for c in result.ranked] == sorted(
        (c.score for c in result.ranked), reverse=True
    )
    last = {c.provider_id: c.score for c in result.ranked}
    assert last["fake-green_portrait"] < 0.5  # green against "red"
    assert last["fake-blue_portrait"] < 0.5


async def test_green_keyword_puts_the_green_clip_first(footage: Footage) -> None:
    await footage.search(["green"])
    result = await footage.with_ranker(ColourRanker()).vet()
    assert result.ranked[0].provider_id == "fake-green_portrait"


async def test_ranking_is_reproducible_across_two_projects_and_two_runs(footage: Footage) -> None:
    await footage.search(["red"])
    first = await footage.vet()
    again = await footage.vet()  # second run reads the stored results
    assert [c.provider_id for c in again.ranked] == [c.provider_id for c in first.ranked]
    assert again.rejected == {}  # nothing is vetted twice
    other = replace(footage, pid=await footage.new_project())
    await other.search(["red"])
    second = await other.vet()
    assert [c.provider_id for c in second.ranked] == [c.provider_id for c in first.ranked]
    assert [round(c.score, 4) for c in second.ranked] == [round(c.score, 4) for c in first.ranked]


async def test_the_fake_ranker_is_a_hash_defined_oracle() -> None:
    """Written by hand: sha256 bytes scaled to [-1, 1]; the same recipe the tests rely on."""
    import hashlib

    digest = hashlib.sha256(b"red").digest()
    expected = [(b - 127.5) / 127.5 for b in digest[:8]]
    assert FakeRanker().embed_text(["red"])[0] == expected
    assert hash_vector(b"red") == expected
    assert len(FakeRanker().embed_text(["x"])[0]) == 8
    assert cosine(expected, expected) == pytest.approx(1.0)


async def test_blobs_embeddings_and_scratch_after_a_run(footage: Footage, tmp_path: Path) -> None:
    await footage.search(["red"])
    await footage.vet()
    row = await footage.by_id("red_portrait")
    blobs = footage.ctx.blobs
    assert blobs.exists(raw_key(footage.pid, "pexels", row.provider_id))
    assert blobs.exists(emb_key(footage.pid, "pexels", row.provider_id))
    assert list((tmp_path / "scratch").iterdir()) == []  # every job directory removed
    assert not footage.redis.keys("saveclock:heavy:*")  # no heavy slot left held


async def test_the_download_is_skipped_when_the_raw_file_exists(footage: Footage) -> None:
    await footage.search(["red"])
    await footage.vet()
    calls: list[str] = []

    class Counting:
        name = "pexels"

        def search(self, query: str, *, page: int = 1, per_page: int = 40) -> list[StockClip]:
            return []

        def download(self, clip: StockClip, blobs: BlobStore, key: str, **kw: object) -> int:
            calls.append(clip.provider_id)
            raise AssertionError("downloaded twice")

    deps = replace(footage.deps, providers=(cast("StockProvider", Counting()),))
    # reset one ranked row to `downloaded`: its raw file is there, so no download happens
    async with footage.ctx.sessionmaker() as session:
        await CandidateRepository(session).mark(
            user_id=OWNER,
            project_id=footage.pid,
            provider="pexels",
            provider_id="fake-red_portrait",
            status="downloaded",
        )
        await session.commit()
    rows = await footage.rows(["downloaded"])
    result = await vet_and_rank(deps, user_id=OWNER, project_id=footage.pid, candidates=rows)
    assert calls == []
    assert [c.provider_id for c in result.ranked] == ["fake-red_portrait"]


def refusing(reason: str) -> StockProvider:
    class Refusing:
        name = "pexels"

        def search(self, query: str, *, page: int = 1, per_page: int = 40) -> list[StockClip]:
            return []

        def download(self, clip: StockClip, blobs: BlobStore, key: str, **kw: object) -> int:
            raise DownloadRefused(reason)

    return cast("StockProvider", Refusing())


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("too_large", ("rejected_quality", "too_large")),
        ("not_mp4", ("rejected_quality", "ffprobe_failed")),
        ("content_type", ("rejected_quality", "ffprobe_failed")),
        ("host_not_allowed", ("rejected_quality", "ffprobe_failed")),
        ("network", ("found", None)),  # transient: stays as it was, retried next run
        ("timeout", ("found", None)),
    ],
)
async def test_download_refusals_reject_permanently_or_skip_transiently(
    footage: Footage, reason: str, expected: tuple[str, str | None]
) -> None:
    await footage.add("red_portrait")
    deps = replace(footage.deps, providers=(refusing(reason),))
    result = await vet_and_rank(
        deps, user_id=OWNER, project_id=footage.pid, candidates=await footage.rows()
    )
    assert (await by_status(footage))["red_portrait"] == expected
    assert result.ranked == []
    assert result.skipped == (1 if expected[0] == "found" else 0)


async def test_a_canceled_download_and_a_cancel_request_stop_the_run(footage: Footage) -> None:
    await footage.add("red_portrait")
    deps = replace(footage.deps, providers=(refusing("canceled"),))
    with pytest.raises(JobCanceled):
        await vet_and_rank(
            deps, user_id=OWNER, project_id=footage.pid, candidates=await footage.rows()
        )
    deps = replace(footage.deps, cancel=lambda: True)
    with pytest.raises(JobCanceled):
        await vet_and_rank(
            deps, user_id=OWNER, project_id=footage.pid, candidates=await footage.rows()
        )


async def test_a_candidate_without_a_url_or_provider_is_rejected_not_crashed(
    footage: Footage,
) -> None:
    await footage.add("red_portrait")
    async with footage.ctx.sessionmaker() as session:
        from sqlalchemy import text

        await session.execute(text("UPDATE clip_candidates SET download_url = NULL"))
        await session.commit()
    await footage.vet()
    assert (await by_status(footage))["red_portrait"] == ("rejected_quality", "ffprobe_failed")
    await footage.add("green_portrait")
    deps = replace(footage.deps, providers=())
    await vet_and_rank(
        deps, user_id=OWNER, project_id=footage.pid, candidates=await footage.rows(["found"])
    )
    assert (await by_status(footage))["green_portrait"] == ("rejected_quality", "ffprobe_failed")


async def test_a_non_video_download_is_rejected_by_the_probe(footage: Footage) -> None:
    await footage.add("red_portrait")
    # a file that passes the magic sniff of the fake store but is not decodable
    footage.ctx.blobs.put(
        raw_key(footage.pid, "pexels", "fake-red_portrait"),
        [b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64],
        max_bytes=1 << 20,
    )
    await footage.vet()
    assert (await by_status(footage))["red_portrait"] == ("rejected_quality", "ffprobe_failed")


async def test_another_user_sees_no_candidates_and_can_change_none(footage: Footage) -> None:
    await footage.search(["red"])
    other = uuid4()
    async with footage.ctx.sessionmaker() as session:
        repo = CandidateRepository(session)
        assert await repo.list_for_project(user_id=other, project_id=footage.pid) == []
        assert (
            await repo.get_by_provider_id(
                user_id=other,
                project_id=footage.pid,
                provider="pexels",
                provider_id="fake-red_portrait",
            )
            is None
        )
        assert not await repo.mark(
            user_id=other,
            project_id=footage.pid,
            provider="pexels",
            provider_id="fake-red_portrait",
            status="selected",
        )
        assert await repo.null_download_urls(user_id=other, project_id=footage.pid) == 0
    assert {r.status for r in await footage.rows()} == {"found"}


async def test_the_heavy_slot_serialises_the_analysis(footage: Footage) -> None:
    """With one slot and three candidates in flight, never two analyses run at once."""
    await footage.search(["red"])
    active, peak = 0, 0
    lock = threading.Lock()

    class Probing(FakeRanker):
        def embed_images(self, paths: object) -> list[list[float]]:
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                import time

                time.sleep(0.15)
                return super().embed_images(paths)  # type: ignore[arg-type]
            finally:
                with lock:
                    active -= 1

    await footage.with_ranker(Probing()).vet()
    assert peak == 1


async def test_concurrency_does_not_change_the_result(footage: Footage) -> None:
    await footage.search(["red"])
    serial = replace(footage, deps=replace(footage.deps, fetch_concurrency=1))
    result = await serial.vet()
    other = replace(footage, pid=await footage.new_project())
    await other.search(["red"])
    parallel = await replace(other, deps=replace(other.deps, fetch_concurrency=4)).vet()
    assert [c.provider_id for c in parallel.ranked] == [c.provider_id for c in result.ranked]

"""Small guards around the footage code: keys, budgets, the fake provider, intermediates."""

import json
from pathlib import Path
from uuid import UUID

import pytest

from saveclock.adapters.blobstore.blob_keys import (
    InvalidKey,
    emb_key,
    is_servable,
    mezz_key,
    raw_key,
)
from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.ffmpeg import MEZZ_TIMEOUT_S, PROBE_TIMEOUT_S, SAMPLE_TIMEOUT_S
from saveclock.adapters.stock.fake import FakeStockProvider
from saveclock.config import FOOTAGE_WAIT_S, HEAVY_TTL_S, NORMALIZE_HOLD_S, VET_HOLD_S
from saveclock.errors import ClipUnavailable, StockUnavailable
from saveclock.repositories.candidates import CandidateRepository

PID = UUID("11111111-1111-4111-8111-111111111111")


def test_candidate_keys_are_built_from_validated_ids_and_are_never_servable() -> None:
    keys = [
        raw_key(PID, "pexels", "3001"),
        mezz_key(PID, "pixabay", "fake-red_portrait"),
        emb_key(PID, "pexels", "3001"),
    ]
    assert keys == [
        f"work/{PID}/raw/pexels_3001.mp4",
        f"work/{PID}/mezz/pixabay_fake-red_portrait.mp4",
        f"work/{PID}/emb/pexels_3001.npy",
    ]
    assert not any(is_servable(k) for k in keys)  # intermediates: the API never streams them


@pytest.mark.parametrize("bad_id", ["", "../x", "a/b", "a b", "x" * 65, "a\n", "%2e%2e"])
def test_a_provider_id_that_could_escape_is_refused(bad_id: str) -> None:
    for build in (raw_key, mezz_key, emb_key):
        with pytest.raises(InvalidKey):
            build(PID, "pexels", bad_id)


def test_an_unknown_provider_is_refused() -> None:
    with pytest.raises(InvalidKey):
        raw_key(PID, "evil", "1")


def test_a_slot_is_never_held_longer_than_its_ttl_and_covers_what_it_spends() -> None:
    assert max(VET_HOLD_S, NORMALIZE_HOLD_S) < HEAVY_TTL_S
    assert NORMALIZE_HOLD_S >= MEZZ_TIMEOUT_S + 2 * PROBE_TIMEOUT_S  # encode + the checks after it
    assert VET_HOLD_S > SAMPLE_TIMEOUT_S  # sampling is part of the vetting hold
    assert FOOTAGE_WAIT_S < HEAVY_TTL_S  # the wait for a slot ends inside the TTL


def test_the_job_errors_use_the_catalogue_codes() -> None:
    assert StockUnavailable("x").code.value == "stock_unavailable"
    assert ClipUnavailable("x").code.value == "clip_unavailable"
    assert StockUnavailable("x").status == 500  # a job error: it never appears as an HTTP status


def write_index(directory: Path) -> None:
    (directory / "a.mp4").write_bytes(b"\x00\x00\x00\x18ftypisom" + b"x" * 40)
    index = {"clips": [{"name": "a", "width": 720, "height": 1280, "duration_s": 5.0, "fps": 30}]}
    (directory / "index.json").write_text(json.dumps(index))


def test_the_fake_provider_serves_its_index_and_rejects_anything_else(tmp_path: Path) -> None:
    write_index(tmp_path)
    provider = FakeStockProvider(tmp_path)
    (clip,) = provider.search("anything")
    assert (clip.provider, clip.provider_id, clip.file_url) == ("pexels", "fake-a", "fake://a.mp4")
    assert provider.search("anything", page=2) == []
    (tmp_path / "blobs").mkdir()
    blobs = FilesystemBlobStore(tmp_path / "blobs", 0)
    assert provider.download(clip, blobs, "work/x/a.mp4", max_bytes=1 << 20, cancel=None) == 52
    from dataclasses import replace

    with pytest.raises(FileNotFoundError):
        provider.download(
            replace(clip, file_url="fake://../index.json"),
            blobs,
            "work/x/b.mp4",
            max_bytes=1 << 20,
            cancel=None,
        )
    with pytest.raises(InterruptedError):
        provider.download(clip, blobs, "work/x/c.mp4", max_bytes=1 << 20, cancel=lambda: True)
    with pytest.raises(FileNotFoundError, match="make fake-stock"):
        FakeStockProvider(tmp_path / "missing")


def test_the_repository_refuses_to_mark_an_unknown_column() -> None:
    import asyncio
    from unittest.mock import MagicMock

    repo = CandidateRepository(MagicMock())
    with pytest.raises(ValueError, match="cannot mark"):
        asyncio.run(
            repo.mark(
                user_id=PID, project_id=PID, provider="pexels", provider_id="1", download_url="x"
            )
        )


def test_laplacian_variance_separates_sharp_from_flat_and_refuses_a_bad_file(
    tmp_path: Path,
) -> None:
    from PIL import Image

    from saveclock.adapters.vision import laplacian_variance

    flat = tmp_path / "flat.png"
    Image.new("RGB", (64, 64), (200, 20, 20)).save(flat)
    sharp = tmp_path / "sharp.png"
    img = Image.new("RGB", (64, 64), (0, 0, 0))
    for x in range(0, 64, 2):
        for y in range(64):
            img.putpixel((x, y), (255, 255, 255))
    img.save(sharp)
    assert laplacian_variance([flat]) == 0.0
    assert laplacian_variance([sharp]) > 1000
    assert laplacian_variance([flat, sharp]) == pytest.approx(laplacian_variance([sharp]) / 2)
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    with pytest.raises(ValueError, match="readable image"):
        laplacian_variance([bad])

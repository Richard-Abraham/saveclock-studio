"""The failure branches of the footage services: transient errors, cancels and the wiring."""

import json
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from saveclock.adapters.ffmpeg import FfCanceled, FfError, FfTimeout
from saveclock.adapters.models import ModelIntegrityError
from saveclock.adapters.safe_http import DownloadRefused
from saveclock.adapters.siglip import FakeRanker, SigLipRanker
from saveclock.adapters.stock.fake import FakeStockProvider
from saveclock.config import Settings
from saveclock.domain.ranking import RankedClip
from saveclock.domain.windows import Window
from saveclock.services import footage as footage_module
from saveclock.services import normalize as normalize_module
from saveclock.services.analysis import JobCanceled
from saveclock.services.footage import (
    SIGLIP_GROUP,
    build_footage_deps,
    get_ranker,
    vet_and_rank,
)
from saveclock.services.normalize import normalize_topk
from tests.conftest import ENV
from tests.integration.footage_harness import OWNER, Footage

if TYPE_CHECKING:
    from redis import Redis

pytestmark = [pytest.mark.integration, pytest.mark.ffmpeg]


async def statuses(f: Footage) -> dict[str, str]:
    return {r.provider_id: r.status for r in await f.rows()}


def raising(exc: Exception) -> Any:
    def boom(*a: object, **k: object) -> None:
        raise exc

    return boom


async def test_a_probe_timeout_is_transient_and_a_probe_cancel_stops_the_job(
    footage: Footage, monkeypatch: pytest.MonkeyPatch
) -> None:
    await footage.search(["red"])
    monkeypatch.setattr(footage_module, "probe_stock", raising(FfTimeout("slow")))
    result = await footage.vet()
    assert result.ranked == []
    assert result.skipped == 7
    assert set((await statuses(footage)).values()) == {"downloaded"}  # retried by the next run
    monkeypatch.setattr(footage_module, "probe_stock", raising(FfCanceled("stop")))
    with pytest.raises(JobCanceled):
        await footage.vet()
    monkeypatch.setattr(footage_module, "probe_stock", raising(FfError("bad")))
    await footage.vet()
    assert set((await statuses(footage)).values()) == {"rejected_quality"}


async def test_analysis_timeouts_cancels_errors_and_empty_samples(
    footage: Footage, monkeypatch: pytest.MonkeyPatch
) -> None:
    await footage.add("red_portrait")
    monkeypatch.setattr(footage_module, "sample_frames", raising(FfTimeout("slow")))
    assert (await footage.vet()).skipped == 1
    monkeypatch.setattr(footage_module, "sample_frames", raising(FfCanceled("stop")))
    with pytest.raises(JobCanceled):
        await footage.vet()
    monkeypatch.setattr(footage_module, "sample_frames", lambda *a, **k: [])
    result = await footage.vet()
    assert result.rejected == {"ffprobe_failed": 1}
    await footage.add("green_portrait")
    monkeypatch.setattr(footage_module, "sample_frames", raising(FfError("bad")))
    result = await footage.vet(["found"])
    assert result.rejected == {"ffprobe_failed": 1}


async def test_a_redirect_loop_is_a_permanent_refusal(footage: Footage) -> None:
    await footage.add("red_portrait")

    class Looping:
        name = "pexels"

        def download(self, *a: object, **k: object) -> int:
            raise DownloadRefused("too_many_redirects")

    deps = replace(footage.deps, providers=(Looping(),))  # type: ignore[arg-type]
    result = await vet_and_rank(
        deps, user_id=OWNER, project_id=footage.pid, candidates=await footage.rows()
    )
    assert result.rejected == {"ffprobe_failed": 1}


def ranked_clip(provider_id: str) -> RankedClip:
    return RankedClip("pexels", provider_id, "red", 0.9, Window(0.2, 3.0))


async def test_normalize_transient_cancel_and_failed_checks(
    footage: Footage, monkeypatch: pytest.MonkeyPatch
) -> None:
    await footage.search(["red"])
    vetted = await footage.vet()
    ranked = vetted.ranked
    monkeypatch.setattr(normalize_module, "build_mezz", raising(FfTimeout("slow")))
    assert (
        await normalize_topk(
            footage.deps, user_id=OWNER, project_id=footage.pid, ranked=ranked[:2], cuts=1
        )
        == []
    )
    monkeypatch.setattr(normalize_module, "build_mezz", raising(FfCanceled("stop")))
    with pytest.raises(JobCanceled):
        await normalize_topk(
            footage.deps, user_id=OWNER, project_id=footage.pid, ranked=ranked[:1], cuts=1
        )
    monkeypatch.undo()
    failing = MagicMock(return_value=[MagicMock(ok=False)])
    monkeypatch.setattr(normalize_module, "video_checks", failing)
    done = await normalize_topk(
        footage.deps, user_id=OWNER, project_id=footage.pid, ranked=ranked[:1], cuts=1
    )
    assert done == []
    row = await footage.by_id(ranked[0].provider_id.removeprefix("fake-"))
    assert (row.status, row.reject_reason) == ("rejected_quality", "ffprobe_failed")


# --- wiring -----------------------------------------------------------------------------------


def settings(**kw: object) -> Settings:
    return Settings(_env_file=None, **{**ENV, **kw})  # type: ignore[arg-type]


def test_build_footage_deps_under_the_fakes(footage: Footage, fake_clips: Path) -> None:
    redis: Redis = footage.redis
    deps = build_footage_deps(
        footage.ctx, redis, pixabay_on=False, cancel=lambda: False, seed="project-1"
    )
    assert isinstance(deps.providers[0], FakeStockProvider)
    assert isinstance(deps.ranker, FakeRanker)
    assert deps.heavy.slots >= 1
    assert deps.seed == "project-1"
    assert deps.fetch_concurrency >= 1
    assert get_ranker(footage.ctx.settings) is deps.ranker  # one per process


def test_the_real_ranker_is_built_lazily_from_a_verified_directory(tmp_path: Path) -> None:
    import hashlib

    group = tmp_path / "siglip"
    group.mkdir()
    (group / "model.safetensors").write_bytes(b"w")
    manifest = {
        "models": [
            {
                "name": "x",
                "group": SIGLIP_GROUP,
                "file": "siglip/model.safetensors",
                "bytes": 1,
                "sha256": hashlib.sha256(b"w").hexdigest(),
            }
        ]
    }
    (tmp_path / "models.manifest.json").write_text(json.dumps(manifest))
    s = settings(models_dir=str(tmp_path), siglip_model="test/siglip-real-branch")
    ranker = get_ranker(s)
    assert isinstance(ranker, SigLipRanker)  # nothing is loaded until the first embed
    assert ranker.model_dir == group
    broken = settings(models_dir=str(tmp_path / "nowhere"), siglip_model="test/siglip-broken")
    with pytest.raises(ModelIntegrityError):
        get_ranker(broken)

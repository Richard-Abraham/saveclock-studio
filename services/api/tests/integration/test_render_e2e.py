"""The whole product path on the real stack with fakes: upload a song, get a draft, render, ask for
Mode A, and download all four files; the files are then checked with ffprobe called directly, not
through any service code."""

import asyncio
import csv
import io
import json
import subprocess
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest

from saveclock.domain.edit_plan import EditPlan
from saveclock.domain.plan_validator import blocking, validate_plan
from tests.conftest import FFMPEG_DIR, client_for, make_app
from tests.factories.audio import click_track
from tests.integration.conftest import REDIS_URL, Harness
from tests.integration.test_draft_e2e import QUEUES, stock, upload, wait_status

pytestmark = [pytest.mark.integration, pytest.mark.ffmpeg]


@pytest.fixture
async def api(harness: Harness) -> AsyncIterator[httpx.AsyncClient]:
    app = make_app(
        database_url=harness.db.url("app_rw"),
        redis_url=REDIS_URL,
        blob_root=str(harness.blob_root),
        disk_low_watermark_gb=0,
    )
    async with client_for(app) as client:
        yield client
    await app.state.deps.close()


def ffprobe(path: Path) -> dict[str, Any]:
    """The file as ffprobe sees it, called directly (an independent oracle)."""
    out = subprocess.run(  # noqa: S603 - a fixed argument list on a file this test wrote
        [str(FFMPEG_DIR / "ffprobe"), "-v", "error", "-protocol_whitelist", "file", "-print_format",
         "json", "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, check=True, timeout=60,
    )  # fmt: skip
    probed: dict[str, Any] = json.loads(out.stdout)
    return probed


async def poll(
    api: httpx.AsyncClient, url: str, key: str, wanted: str, within_s: float = 240
) -> dict[str, Any]:
    deadline = time.monotonic() + within_s
    body: dict[str, Any] = {}
    while time.monotonic() < deadline:
        body = (await api.get(url)).json()
        if body[key] == wanted:
            return body
        assert body["state"] not in {"failed", "canceled"}, body
        await asyncio.sleep(0.3)
    pytest.fail(f"{url} never had {key} == {wanted}: {body}")


async def test_upload_to_four_downloads_on_the_real_stack(
    harness: Harness, api: httpx.AsyncClient, fake_clips: Path, tmp_path: Path
) -> None:
    harness.start_worker([*QUEUES, "maintenance"], **stock(fake_clips))
    wav = tmp_path / "click128.wav"
    click_track(wav, bpm=128.0, duration=30.0)
    pid = await upload(api, wav)
    await wait_status(harness.db, pid, "draft_ready", 180)

    created = await api.post(f"/api/v1/projects/{pid}/renders", json={})
    assert created.status_code == 202
    rid = UUID(created.json()["render_id"])
    render = await poll(api, f"/api/v1/renders/{rid}", "state", "ready")
    assert render["files"] == ["silent_video", "cutlist_json", "cutlist_csv"]
    assert render["verify"]["passed"] is True
    assert (await api.get(f"/api/v1/projects/{pid}")).json()["ui_status"] == "ready"

    mode_a = await api.post(f"/api/v1/renders/{rid}/mode-a")
    assert (mode_a.status_code, mode_a.json()["mode_a_state"]) == (202, "queued")
    render = await poll(api, f"/api/v1/renders/{rid}", "mode_a_state", "ready", 120)
    assert render["files"][-1] == "with_song"

    saved: dict[str, Path] = {}
    for kind, name in {
        "silent_video": "master.mp4", "cutlist_json": "cutlist.json",
        "cutlist_csv": "cutlist.csv", "with_song": "with_song.mp4",
    }.items():  # fmt: skip
        r = await api.get(f"/api/v1/renders/{rid}/download", params={"kind": kind})
        assert r.status_code == 200, kind
        saved[kind] = tmp_path / name
        await asyncio.to_thread(saved[kind].write_bytes, r.content)

    master = ffprobe(saved["silent_video"])
    kinds = [s["codec_type"] for s in master["streams"]]
    video = master["streams"][0]
    assert kinds == ["video"]  # one video stream and no audio
    assert (video["width"], video["height"]) == (1080, 1920)
    assert (video["r_frame_rate"], video["codec_name"], video["profile"]) == (
        "30/1",
        "h264",
        "High",
    )
    assert video["pix_fmt"] == "yuv420p"
    with_song = ffprobe(saved["with_song"])
    assert sorted(s["codec_type"] for s in with_song["streams"]) == ["audio", "video"]
    audio = next(s for s in with_song["streams"] if s["codec_type"] == "audio")
    assert (audio["codec_name"], audio["profile"]) == ("aac", "LC")
    plan = EditPlan.model_validate(
        {
            k: v
            for k, v in (await api.get(f"/api/v1/projects/{pid}/plan")).json().items()
            if k != "frozen"
        }
    )
    assert blocking(validate_plan(plan, allow_repeats=True, beats_s=plan.beat_grid.beats_s)) == []
    assert int(video["nb_frames"]) == plan.total_frames == 900

    listed = json.loads(saved["cutlist_json"].read_text())["cuts"]
    table = list(csv.DictReader(io.StringIO(saved["cutlist_csv"].read_text())))
    assert [c["start_frame"] for c in listed] == [c.out_start_frame for c in plan.cuts]
    assert [int(r["start_frame"]) for r in table] == [c.out_start_frame for c in plan.cuts]
    assert "audio" not in saved["cutlist_json"].read_text()
    sizes = {k: p.stat().st_size for k, p in saved.items()}
    print(
        "E2E",
        f"master {video['width']}x{video['height']} {video['r_frame_rate']} fps "
        f"{video['codec_name']}/{video['profile']} streams={kinds};",
        f"with_song streams={sorted(s['codec_type'] for s in with_song['streams'])} "
        f"audio={audio['codec_name']}/{audio['profile']};",
        f"sizes {sizes}",
    )

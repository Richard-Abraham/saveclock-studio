"""The `saveclock` CLI end to end (plan 009): the real wrapper as a subprocess, from another
directory, against a real uvicorn API and real worker subprocesses (Postgres, Redis, FFmpeg,
generated clips). Only Beat This (a click picker) and the stock API are fakes."""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import FFMPEG_DIR
from tests.factories.audio import click_track
from tests.integration.conftest import Harness, LiveApi
from tests.integration.test_draft_e2e import QUEUES, stock

pytestmark = [pytest.mark.integration, pytest.mark.ffmpeg]
WRAPPER = Path(__file__).resolve().parents[4] / "scripts" / "saveclock"
ID_ZERO = "00000000-0000-4000-8000-000000000000"


def saveclock(api: LiveApi, cwd: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - the repo's own wrapper, fixed arguments
        [str(WRAPPER), "--api-url", api.url, *argv],
        cwd=cwd, capture_output=True, text=True, timeout=900, check=False,
    )  # fmt: skip


def as_json(done: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(done.stdout)
    return doc


def ffprobe(path: Path) -> dict[str, Any]:
    out = subprocess.run(  # noqa: S603 - a fixed argument list on a file this test wrote
        [str(FFMPEG_DIR / "ffprobe"), "-v", "error", "-protocol_whitelist", "file", "-print_format",
         "json", "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, check=True, timeout=60,
    )  # fmt: skip
    probed: dict[str, Any] = json.loads(out.stdout)
    return probed


async def test_new_to_export_from_another_directory(  # noqa: PLR0915
    harness: Harness, fake_clips: Path, tmp_path: Path
) -> None:
    harness.start_worker([*QUEUES, "maintenance"], **stock(fake_clips))
    songs, work = tmp_path / "songs", tmp_path / "work"
    songs.mkdir()
    work.mkdir()
    click_track(songs / "click128.wav", bpm=128.0, duration=30.0)
    with LiveApi(harness) as api:

        async def cli(*argv: str) -> subprocess.CompletedProcess[str]:
            return await asyncio.to_thread(saveclock, api, work, *argv)

        # a relative song path resolves in the caller's directory, not the project's
        done = await cli("new", "../songs/click128.wav", "--vibe", "calm night drive", "--json")
        assert done.returncode == 0, done.stderr
        pid = as_json(done)["project_id"]

        done = await cli("status", pid, "--watch", "--json")
        assert done.returncode == 0, done.stderr + done.stdout
        assert as_json(done)["project"]["ui_status"] == "draft"

        shown = as_json(await cli("show", pid, "--json"))
        assert abs(shown["analysis"]["tempo_bpm"] - 128.0) < 1.0
        assert shown["analysis"]["sections"]
        assert shown["project"]["options"]["vibe"] == "calm night drive"
        assert shown["plan"]["version"] == 1

        words = ["night drive", "city lights", "neon street", "rain window", "taxi"]
        done = await cli("keywords", "set", pid, *words, "--json")
        assert done.returncode == 0, done.stderr + done.stdout
        assert as_json(done)["applied"] is True
        shown = as_json(await cli("show", pid, "--json"))
        assert shown["plan"]["version"] == 1  # an unfrozen plan is replaced in place
        assert shown["keywords"]["source"] == "explicit"

        plan = as_json(await cli("plan", pid, "--json"))
        assert plan["version"] == 1
        assert plan["keyword_source"] == "explicit"
        assert plan["total_frames"] == 900

        done = await cli("render", pid, "--json")
        assert done.returncode == 0, done.stderr + done.stdout
        assert as_json(done)["state"] == "ready"

        done = await cli("export", pid, "--mode", "a", "--out", "out", "--json")
        assert done.returncode == 2  # `out` does not exist yet: nothing is created for you
        (work / "out").mkdir()
        done = await cli("export", pid, "--mode", "a", "--out", "out", "--json")
        assert done.returncode == 0, done.stderr + done.stdout
        with_song = Path(as_json(done)["files"][0]["path"])
        done = await cli("export", pid, "--mode", "b", "--out", "out", "--json")
        assert done.returncode == 0, done.stderr + done.stdout
        exported = as_json(done)
        paths = {f["kind"]: Path(f["path"]) for f in exported["files"]}
        assert all(p.parent == (work / "out").resolve() and p.is_file() for p in paths.values())
        assert exported["credits_text"]
        refused = await cli("export", pid, "--mode", "b", "--out", "out")
        assert refused.returncode == 2  # an existing file is not overwritten
        assert (await cli("export", pid, "--mode", "b", "--out", "out", "--force")).returncode == 0

        master = ffprobe(paths["silent_video"])
        assert [s["codec_type"] for s in master["streams"]] == ["video"]  # no audio
        audio = [s for s in ffprobe(with_song)["streams"] if s["codec_type"] == "audio"]
        assert [(a["codec_name"], a["profile"]) for a in audio] == [("aac", "LC")]
        listed = json.loads(paths["cutlist_json"].read_text())["cuts"]
        assert [c["start_frame"] for c in listed] == [c["out_start_frame"] for c in plan["cuts"]]
        assert [c["end_frame"] for c in listed] == [c["out_end_frame"] for c in plan["cuts"]]

        listing = await cli("status")
        assert listing.returncode == 0
        assert pid in listing.stdout

        bad = await cli("keywords", "set", pid, "Not Valid!", "--json")
        assert bad.returncode == 1
        assert as_json(bad)["error"]["code"] == "validation_error"
        missing = await cli("status", ID_ZERO, "--json")
        assert missing.returncode == 1
        assert as_json(missing)["error"]["code"] == "not_found"


async def test_a_draft_that_fails_makes_status_exit_1_with_the_failure(
    harness: Harness, fake_clips: Path, tmp_path: Path
) -> None:
    empty = tmp_path / "no-usable-clips"
    empty.mkdir()
    (empty / "landscape.mp4").write_bytes((fake_clips / "landscape.mp4").read_bytes())
    (empty / "index.json").write_text(
        json.dumps(
            {
                "clips": [
                    {
                        "name": "landscape",
                        "width": 1280,
                        "height": 720,
                        "duration_s": 6.0,
                        "fps": 30,
                    }
                ]
            }
        )
    )
    harness.start_worker(QUEUES, **stock(empty))
    click_track(tmp_path / "click128.wav", bpm=128.0, duration=30.0)
    with LiveApi(harness) as api:
        done = await asyncio.to_thread(saveclock, api, tmp_path, "new", "click128.wav", "--json")
        assert done.returncode == 0, done.stderr
        pid = as_json(done)["project_id"]
        watched = await asyncio.to_thread(
            saveclock, api, tmp_path, "status", pid, "--watch", "--json"
        )
        assert watched.returncode == 1, watched.stderr + watched.stdout
        project = as_json(watched)["project"]
        assert project["ui_status"] == "failed"
        assert project["status_reason"] == "no_usable_clips"
        plain = await asyncio.to_thread(saveclock, api, tmp_path, "status", pid)
        assert plain.returncode == 1
        assert "no_usable_clips" in plain.stdout

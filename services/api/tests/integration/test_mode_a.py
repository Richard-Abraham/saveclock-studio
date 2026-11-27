"""Mode A (`POST /renders/{id}/mode-a`, the `remux_with_song` job): states, repeats, the source
file, the argv, and a Block failure."""

import json
from typing import Any
from uuid import UUID

import pytest

from saveclock.adapters.ffmpeg import remux_cmd as real_remux_cmd
from saveclock.services.render_job import VerificationFailed
from tests.integration.render_harness import Renders

pytestmark = [pytest.mark.integration, pytest.mark.ffmpeg]


async def ready_render(renderer: Renders, kind: str = "wav") -> tuple[UUID, UUID]:
    d = renderer.draft
    if kind == "wav":
        pid = await d.drafted()
    else:
        pid = await d.drafted(pid=await renderer.upload_source(kind))  # type: ignore[arg-type]
    return pid, await renderer.ready(pid)


async def test_states_run_queued_to_ready_and_the_file_is_published(renderer: Renders) -> None:
    d = renderer.draft
    pid, rid = await ready_render(renderer)
    r = await renderer.mode_a(rid)
    assert (r.status_code, r.json()) == (202, {"render_id": str(rid), "mode_a_state": "queued"})
    job = await renderer.job_of(rid, "remux")
    assert renderer.api_sent[-1][0] == "remux_with_song"
    assert (await renderer.render_row(rid))["mode_a_state"] == "queued"
    await renderer.run_remux(job)
    row = await renderer.render_row(rid)
    assert (row["mode_a_state"], row["mode_a_key"]) == ("ready", f"renders/{rid}/with_song.mp4")
    assert renderer.path(rid, "with_song.mp4").stat().st_size > 0
    assert await d.job(job) == ("ok", None)
    assert await d.status(pid) == ("ready", None)  # Mode A never moves the project
    assert "mode_a_ready" in d.recorder.kinds()
    verify = json.loads(row["v"])["mode_a"]
    assert not [c for c in verify["checks"] if not c["ok"] and c["level"] == "block"]
    got = (await renderer.client.get(f"/api/v1/renders/{rid}")).json()
    assert got["files"][-1] == "with_song"
    assert got["mode_a_state"] == "ready"


async def test_a_repeat_returns_the_existing_state_and_enqueues_nothing(renderer: Renders) -> None:
    _, rid = await ready_render(renderer)
    first = await renderer.mode_a(rid)
    again = await renderer.mode_a(rid)
    assert again.json() == first.json()
    assert [a for a, _ in renderer.api_sent].count("remux_with_song") == 1
    await renderer.run_remux(await renderer.job_of(rid, "remux"))
    done = await renderer.mode_a(rid)  # ready: returned as it is
    assert (done.status_code, done.json()["mode_a_state"]) == (202, "ready")
    assert [a for a, _ in renderer.api_sent].count("remux_with_song") == 1


async def test_after_a_failure_a_repeat_queues_one_new_attempt(renderer: Renders) -> None:
    d = renderer.draft
    _, rid = await ready_render(renderer)
    await renderer.mode_a(rid)
    first = await renderer.job_of(rid, "remux")
    await renderer.kill_job(first)  # retries exhausted
    assert (await renderer.render_row(rid))["mode_a_state"] == "failed"
    again = await renderer.mode_a(rid)
    assert again.json()["mode_a_state"] == "queued"
    second = await renderer.job_of(rid, "remux")
    assert second != first
    assert (await d.sql("SELECT count(*) FROM jobs WHERE stage = 'remux'"))[0][0] == 2
    await renderer.mode_a(rid)  # queued now: nothing more
    assert (await d.sql("SELECT count(*) FROM jobs WHERE stage = 'remux'"))[0][0] == 2
    await renderer.run_remux(second)
    assert (await renderer.render_row(rid))["mode_a_state"] == "ready"


async def test_mode_a_on_a_render_that_is_not_ready_is_409(renderer: Renders) -> None:
    d = renderer.draft
    rid, _ = await renderer.start(await d.drafted())
    r = await renderer.mode_a(rid)
    assert (r.status_code, r.json()["error"]["details"]["reason"]) == (409, "not_ready")
    assert (await d.sql("SELECT count(*) FROM jobs WHERE stage = 'remux'"))[0][0] == 0


async def test_mode_a_never_creates_a_render_or_a_render_job(renderer: Renders) -> None:
    d = renderer.draft
    _, rid = await ready_render(renderer)
    renders_before = (await d.sql("SELECT count(*) FROM renders"))[0][0]
    render_jobs_before = (await d.sql("SELECT count(*) FROM jobs WHERE stage = 'render'"))[0][0]
    await renderer.mode_a(rid)
    await renderer.run_remux(await renderer.job_of(rid, "remux"))
    assert (await d.sql("SELECT count(*) FROM renders"))[0][0] == renders_before
    assert (await d.sql("SELECT count(*) FROM jobs WHERE stage = 'render'"))[0][
        0
    ] == render_jobs_before
    master = renderer.path(rid, "master.mp4")
    assert master.is_file()  # Mode B needs no call: the silent master is still there


@pytest.mark.parametrize("kind", ["m4a", "mp3", "wav"])
async def test_every_source_type_is_remuxed_within_a_frame(renderer: Renders, kind: str) -> None:
    _, rid = await ready_render(renderer, kind)
    await renderer.mode_a(rid)
    await renderer.run_remux(await renderer.job_of(rid, "remux"))
    row = await renderer.render_row(rid)
    assert row["mode_a_state"] == "ready"
    mode_a = json.loads(row["v"])["mode_a"]
    assert abs(mode_a["offset_start_ms"]) <= 1000 / 30
    assert abs(mode_a["offset_end_ms"]) <= 1000 / 30
    assert abs(mode_a["drift_ms_per_60s"]) <= 1000 / 30


async def test_the_argv_has_no_processing_and_the_original_is_the_source(
    renderer: Renders, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = renderer.draft
    seen: list[list[str]] = []

    def spy(*a: Any, **kw: Any) -> list[str]:
        cmd: list[str] = real_remux_cmd(*a, **kw)
        seen.append(cmd)
        return cmd

    monkeypatch.setattr("saveclock.services.render_job.remux_cmd", spy)
    pid, rid = await ready_render(renderer)
    (d.env.blob_root / "work" / str(pid) / "canonical.flac").unlink()  # not the source of Mode A
    await renderer.mode_a(rid)
    await renderer.run_remux(await renderer.job_of(rid, "remux"))
    assert (await renderer.render_row(rid))["mode_a_state"] == "ready"
    (cmd,) = seen
    for flag in ("-af", "-vf", "-filter", "-filter_complex"):
        assert flag not in cmd
    assert not any(x in " ".join(cmd) for x in ("volume", "loudnorm", "afade"))
    source = str(d.env.blob_root / "songs" / str(pid) / "source.wav")
    assert source in cmd
    assert "canonical" not in " ".join(cmd)


async def test_a_remux_that_re_encodes_the_video_is_a_block_and_ends_mode_a(
    renderer: Renders, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = renderer.draft

    def reencoding(*a: Any, **kw: Any) -> list[str]:
        cmd: list[str] = real_remux_cmd(*a, **kw)
        i = cmd.index("-c:v")
        return [*cmd[: i + 1], "libx264", "-preset", "ultrafast", "-crf", "30", *cmd[i + 2 :]]
        # not copied; ultrafast keeps the re-encode under REMUX_FFMPEG_S on a loaded machine

    monkeypatch.setattr("saveclock.services.render_job.remux_cmd", reencoding)
    pid, rid = await ready_render(renderer)
    await renderer.mode_a(rid)
    job = await renderer.job_of(rid, "remux")
    with pytest.raises(VerificationFailed, match="QM-087"):
        await renderer.run_remux(job)
    stored = json.loads((await renderer.render_row(rid))["v"])["mode_a"]
    assert [c for c in stored["checks"] if not c["ok"] and c["level"] == "block"]
    assert not renderer.path(rid, "with_song.mp4").exists()  # never delivered
    await renderer.kill_job(job)  # the retry failed too
    row = await renderer.render_row(rid)
    assert (row["state"], row["mode_a_state"]) == ("ready", "failed")  # the silent master stays
    assert await d.status(pid) == ("ready", None)
    assert renderer.path(rid, "master.mp4").is_file()


async def test_an_enqueue_failure_fails_mode_a_and_a_repeat_queues_it_again(
    renderer: Renders, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, rid = await ready_render(renderer)
    enqueuer = renderer.draft.env.enqueuer
    real_send = enqueuer.send

    def broken(*a: str) -> None:
        raise ConnectionError("redis is down")

    monkeypatch.setattr(enqueuer, "send", broken)
    assert (await renderer.mode_a(rid)).status_code == 500
    assert (await renderer.render_row(rid))["mode_a_state"] == "failed"
    monkeypatch.setattr(enqueuer, "send", real_send)
    again = await renderer.mode_a(rid)
    assert (again.status_code, again.json()["mode_a_state"]) == (202, "queued")

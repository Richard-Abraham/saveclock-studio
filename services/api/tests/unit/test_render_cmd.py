"""The render and remux command lines (ARCH §11), with no process: argv and filter literals."""

import re
import time
from pathlib import Path

import pytest

from saveclock.adapters import ffmpeg
from saveclock.adapters.ffmpeg import (
    MP4_FMT,
    FfError,
    ProgressTail,
    Tools,
    check_args,
    filter_graph,
    parse_progress,
    remux_cmd,
    render_cmd,
)
from saveclock.domain import edit_plan as ep
from tests.unit.domain.plan_support import plan

T = Tools("/opt/ffmpeg", "/opt/ffprobe")
OUT, PROGRESS = Path("/s/master.mp4"), Path("/s/progress.txt")
MASTER, SOURCE = Path("/b/master.mp4"), Path("/b/source.m4a")


def three_cuts() -> ep.EditPlan:
    p = plan(128.0, "e3", seconds=15).plan
    return p.model_copy(update={"cuts": p.cuts[:3]})


def n_cuts(n: int) -> ep.EditPlan:
    p = plan(128.0, "e3", seconds=15).plan
    cuts = [p.cuts[i % len(p.cuts)].model_copy(update={"index": i}) for i in range(n)]
    return p.model_copy(update={"cuts": cuts})


def test_the_filter_graph_of_three_cuts_is_the_literal() -> None:
    p = three_cuts()
    a, b, c = p.cuts
    length = [x.out_end_frame - x.out_start_frame for x in (a, b, c)]
    s = [x.clip.in_frame for x in (a, b, c)]
    expected = (
        f"[0:v]trim=start_frame={s[0]}:end_frame={s[0] + length[0]},setpts=PTS-STARTPTS[v0];"
        f"[1:v]trim=start_frame={s[1]}:end_frame={s[1] + length[1]},setpts=PTS-STARTPTS[v1];"
        f"[2:v]trim=start_frame={s[2]}:end_frame={s[2] + length[2]},setpts=PTS-STARTPTS[v2];"
        "[v0][v1][v2]concat=n=3:v=1:a=0[vc];[vc]null[vout]"
    )
    assert filter_graph(p) == expected


def test_every_trim_counts_frames_never_seconds() -> None:
    graph = filter_graph(plan(128.0, "e3", seconds=30).plan)
    assert re.search(r"trim=start=|:end=|duration=", graph) is None
    assert len(re.findall(r"trim=start_frame=\d+:end_frame=\d+", graph)) == graph.count("trim=")


def test_the_render_command_has_one_input_per_cut_and_the_template_flags() -> None:
    p = three_cuts()
    paths = [Path(f"/m/{i}.mp4") for i in range(3)]
    cmd = render_cmd(T, p, paths, OUT, progress=PROGRESS, threads=4)
    inputs = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-i"]
    assert inputs == [str(x) for x in paths]
    assert cmd.count("-f") == 4  # three forced input formats and the output container
    assert [cmd[i + 1] for i, a in enumerate(cmd) if a == "-f"][:3] == [MP4_FMT] * 3
    assert cmd[cmd.index("-threads") + 1] == "4"
    assert cmd[cmd.index("-frames:v") + 1] == str(p.total_frames)
    assert cmd[cmd.index("-progress") + 1] == str(PROGRESS)
    assert "-nostats" in cmd
    assert cmd[cmd.index("-crf") + 1] == "20"
    assert cmd[-1] == str(OUT)
    assert cmd[cmd.index("-map") + 1] == "[vout]"
    check_args(cmd)


def test_the_render_has_no_audio_and_gop_60_is_the_only_gop_flag() -> None:
    cmd = render_cmd(
        T, three_cuts(), [Path(f"/m/{i}.mp4") for i in range(3)], OUT, progress=PROGRESS, threads=2
    )
    assert "-an" in cmd
    for flag in ("-af", "-c:a", "-filter:a", "-b:a"):
        assert flag not in cmd
    assert cmd[cmd.index("-g") + 1] == "60"
    for flag in ("-sc_threshold", "-keyint_min", "-bf"):  # P7-6: the template stays as ARCH has it
        assert flag not in cmd
    assert cmd.count("-protocol_whitelist") == 1


def test_sixty_inputs_are_the_cap_and_the_mezzanine_count_must_match() -> None:
    sixty = n_cuts(60)
    render_cmd(
        T, sixty, [Path(f"/m/{i}.mp4") for i in range(60)], OUT, progress=PROGRESS, threads=1
    )
    with pytest.raises(FfError):
        render_cmd(
            T,
            n_cuts(61),
            [Path(f"/m/{i}.mp4") for i in range(61)],
            OUT,
            progress=PROGRESS,
            threads=1,
        )
    with pytest.raises(FfError):
        render_cmd(T, sixty, [Path("/m/0.mp4")], OUT, progress=PROGRESS, threads=1)
    with pytest.raises(FfError):
        render_cmd(
            T, three_cuts().model_copy(update={"cuts": []}), [], OUT, progress=PROGRESS, threads=1
        )


def common() -> list[str]:
    return [T.ffmpeg, *ffmpeg.COMMON]


def test_the_remux_copy_path_is_the_architecture_literal() -> None:
    cmd = remux_cmd(
        T, MASTER, SOURCE, MP4_FMT, audio_start_s=12.5, total_frames=900, out=OUT, aac_copy=True
    )
    assert cmd == [
        *common(),
        *("-f", MP4_FMT, "-i", str(MASTER)),
        *("-ss", "12.500000", "-t", "30.000000", "-f", MP4_FMT, "-i", str(SOURCE)),
        *("-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "copy"),
        *("-t", "30.000000", "-movflags", "+faststart", "-f", "mp4", str(OUT)),
    ]
    check_args(cmd)


def test_the_remux_transcode_path_is_the_architecture_literal() -> None:
    cmd = remux_cmd(
        T, MASTER, Path("/b/source.mp3"), "mp3", audio_start_s=0.0, total_frames=1800, out=OUT,
        aac_copy=False,
    )  # fmt: skip
    assert cmd == [
        *common(),
        *("-f", MP4_FMT, "-i", str(MASTER)),
        *("-ss", "0.000000", "-t", "60.000000", "-f", "mp3", "-i", "/b/source.mp3"),
        *("-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy"),
        *("-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"),
        *("-t", "60.000000", "-movflags", "+faststart", "-f", "mp4", str(OUT)),
    ]
    check_args(cmd)


@pytest.mark.parametrize("aac_copy", [True, False])
def test_a_remux_never_processes_the_audio_or_the_video(aac_copy: bool) -> None:
    cmd = remux_cmd(
        T, MASTER, SOURCE, MP4_FMT, audio_start_s=1.0, total_frames=900, out=OUT, aac_copy=aac_copy
    )
    for flag in ("-af", "-vf", "-filter", "-filter_complex", "-filter:a", "-filter:v"):
        assert flag not in cmd
    assert not any(re.search(r"volume|loudnorm|afade|equalizer|aresample", a) for a in cmd)
    assert cmd.count("-protocol_whitelist") == 1
    assert cmd[cmd.index("-c:v") + 1] == "copy"


def test_the_progress_file_is_parsed_to_the_last_frame_and_the_end() -> None:
    running = "frame=10\nfps=30\nprogress=continue\nframe=95\nprogress=continue\n"
    assert parse_progress(running) == (95, False)
    assert parse_progress(running + "frame=150\nprogress=end\n") == (150, True)
    assert parse_progress("") == (0, False)
    assert parse_progress("frame=N/A\nprogress=continue\n") == (0, False)


def test_the_progress_tail_reports_the_fraction_and_stops_at_the_end(tmp_path: Path) -> None:
    path = tmp_path / "progress.txt"
    seen: list[float] = []
    path.write_text("frame=30\nprogress=continue\n")
    with ProgressTail(path, 60, seen.append, poll_s=0.01):
        deadline = 200
        while not seen and deadline:
            deadline -= 1
            time.sleep(0.01)
        path.write_text("frame=90\nprogress=end\n")  # more than the total: clamped to 1.0
        while 1.0 not in seen and deadline:
            deadline -= 1
            time.sleep(0.01)
    assert seen[0] == 0.5
    assert seen[-1] == 1.0
    assert all(0.0 <= f <= 1.0 for f in seen)


def test_a_missing_progress_file_is_not_an_error(tmp_path: Path) -> None:
    seen: list[float] = []
    with ProgressTail(tmp_path / "none.txt", 10, seen.append, poll_s=0.01):
        time.sleep(0.05)
    assert seen == []

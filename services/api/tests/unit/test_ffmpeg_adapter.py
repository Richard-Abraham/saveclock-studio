"""The audited FFmpeg runner: argument rules, process hygiene, and the real binary on real files."""

import contextlib
import json
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from saveclock.adapters import ffmpeg
from saveclock.adapters.ffmpeg import (
    COMMON,
    PROBE_COMMON,
    DecodeFailed,
    FfError,
    Tools,
    canonicalize,
    check_args,
    ffmpeg_cmd,
    probe_audio,
    run,
)
from saveclock.domain.audio_rules import check_audio, codec_label, first_audio
from saveclock.domain.media_sniff import NotSniffable, sniff
from tests.factories import media
from tests.factories.audio import click_track

T = Tools("/opt/ffmpeg", "/opt/ffprobe")


# --- argument rules (no process) --------------------------------------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        [],
        ["/opt/ffmpeg -i x.wav"],  # a joined command line as the executable
        ["/opt/ffmpeg", *COMMON, "-i x.wav"],  # joined option and value
        ["/opt/ffmpeg", *COMMON, "/opt/ffmpeg -i x"],
        ["/opt/ffmpeg", "-i", "x.wav"],  # no -protocol_whitelist at all
        ["/opt/ffmpeg", *COMMON, "-i", "http://127.0.0.1/x.mp3"],  # URL input
        ["/opt/ffmpeg", *COMMON, "-i", "concat:a|b"],
        ["/opt/ffmpeg", *COMMON, "-protocol_whitelist", "file", "-i", "x"],  # a second whitelist
        ["/opt/ffmpeg", "-protocol_whitelist", "file,http", "-i", "x"],
        ["/opt/ffmpeg", *COMMON, "-safe", "0", "-i", "x"],
        ["/opt/ffmpeg", *COMMON, "-headers", "X: y", "-i", "x"],
        ["/opt/ffprobe", "-protocol_whitelist", "file,pipe", "x"],
    ],
)
def test_check_args_refuses(cmd: list[str]) -> None:
    with pytest.raises(FfError):
        check_args(cmd)


def test_check_args_accepts_our_templates() -> None:
    check_args(ffmpeg_cmd(T, "-f", "wav", "-i", "/data/blobs/a.wav", "/scratch/x/out.flac"))
    check_args([T.ffprobe, *PROBE_COMMON, "-f", "mp3", "/data/blobs/a.mp3"])
    check_args(["/opt/ffmpeg", "-version"])
    assert COMMON.count("-protocol_whitelist") == 1
    assert COMMON[COMMON.index("-protocol_whitelist") + 1] == "file"


# --- process hygiene --------------------------------------------------------------------------


def test_no_shell_interprets_the_arguments(tmp_path: Path) -> None:
    marker = tmp_path / "pwned"
    res = run(["/bin/echo", f"a; touch {marker}"], 10)
    assert res.stdout.decode().strip() == f"a; touch {marker}"
    assert not marker.exists()


def test_the_child_runs_with_an_empty_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAVECLOCK_SECRET_PROBE", "leak")
    assert run(["/usr/bin/env"], 10).stdout == b""


def _alive(pid: int) -> bool:
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (FileNotFoundError, ProcessLookupError):
        return False
    return state != "Z"  # a zombie is dead, waiting only to be reaped


SPAWN = (
    "import subprocess, sys, time\n"
    "p = subprocess.Popen(['/bin/sleep', '30'])\n"
    "open(sys.argv[1], 'w').write(str(p.pid))\n"
    "time.sleep(30)\n"
)


def _spawner(pidfile: Path) -> list[str]:
    return [sys.executable, "-c", SPAWN, str(pidfile)]


def _grandchild(pidfile: Path) -> int:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if pidfile.exists() and pidfile.read_text():
            return int(pidfile.read_text())
        time.sleep(0.05)
    pytest.fail("the grandchild never started")


def _gone_within(pid: int, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.05)
    return False


def test_timeout_kills_the_whole_process_group(tmp_path: Path) -> None:
    pidfile = tmp_path / "pid"
    with pytest.raises(FfError, match="timeout"):
        run(_spawner(pidfile), 1.5)
    assert _gone_within(_grandchild(pidfile), 2)


def test_cancel_kills_the_whole_process_group(tmp_path: Path) -> None:
    pidfile = tmp_path / "pid"
    started = time.monotonic()
    with pytest.raises(FfError, match="canceled"):
        run(_spawner(pidfile), 60, cancel=lambda: pidfile.exists() and bool(pidfile.read_text()))
    assert time.monotonic() - started < 10
    assert _gone_within(_grandchild(pidfile), 2)


def test_an_interrupt_kills_the_group_too(tmp_path: Path) -> None:
    pidfile = tmp_path / "pid"

    def interrupt() -> bool:
        if pidfile.exists() and pidfile.read_text():
            raise KeyboardInterrupt
        return False

    with pytest.raises(KeyboardInterrupt):
        run(_spawner(pidfile), 60, cancel=interrupt)
    assert _gone_within(_grandchild(pidfile), 2)


def test_a_failing_command_reports_the_stderr_tail() -> None:
    with pytest.raises(FfError, match="exit 1"):
        run(["/bin/false"], 10)
    assert run(["/bin/false"], 10, check=False).returncode == 1


def test_prlimit_wraps_the_command_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []
    real = subprocess.Popen

    def spy(argv: list[str], **kw: object) -> object:
        seen.append(argv)
        return real(argv, **kw)  # type: ignore[call-overload]

    monkeypatch.setattr(subprocess, "Popen", spy)
    run(["/bin/true"], 10)
    if ffmpeg.PRLIMIT.exists():
        assert seen[0][:4] == [str(ffmpeg.PRLIMIT), "--as=4294967296", "--cpu=600", "--"]
    assert seen[0][-1] == "/bin/true"


def test_the_render_gets_a_larger_address_space_than_a_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[list[str]] = []
    real = subprocess.Popen

    def spy(argv: list[str], **kw: object) -> object:
        seen.append(argv)
        return real(argv, **kw)  # type: ignore[call-overload]

    monkeypatch.setattr(subprocess, "Popen", spy)
    run(["/bin/true"], 10, as_bytes=ffmpeg.RENDER_AS_BYTES)
    if ffmpeg.PRLIMIT.exists():
        assert f"--as={ffmpeg.RENDER_AS_BYTES}" in seen[0]
    assert ffmpeg.RENDER_AS_BYTES > ffmpeg.LIMIT_AS_BYTES


# --- the real binary --------------------------------------------------------------------------


@pytest.mark.ffmpeg
def test_probe_and_canonicalize_a_wav(ffmpeg_tools: Tools, tmp_path: Path) -> None:
    src = tmp_path / "in.wav"
    click_track(src, duration=20)
    probe = probe_audio(ffmpeg_tools, src, "wav")
    assert probe.format_name == "wav"
    assert probe.duration_s == pytest.approx(20.0, abs=0.05)
    assert check_audio(probe, min_s=15, max_s=600) is None

    out = tmp_path / "canonical.flac"
    canonicalize(ffmpeg_tools, src, "wav", out)
    cmd = [ffmpeg_tools.ffprobe, *PROBE_COMMON, "-f", "flac", "-print_format", "json"]
    cmd += ["-show_entries", "stream=codec_name,sample_rate,channels:format_tags", str(out)]
    data = json.loads(run(cmd, 30).stdout)
    stream = data["streams"][0]
    assert (stream["codec_name"], stream["sample_rate"], stream["channels"]) == ("flac", "48000", 2)
    tags = {k.lower(): v for k, v in data.get("format", {}).get("tags", {}).items()}
    assert tags == {}  # no title, artist, comment or encoder tag


@pytest.mark.ffmpeg
def test_mp3_with_a_small_cover_is_accepted_and_the_picture_is_dropped(
    ffmpeg_tools: Tools, tmp_path: Path
) -> None:
    src = media.mp3_with_cover(ffmpeg_tools, tmp_path)
    probe = probe_audio(ffmpeg_tools, src, "mp3")
    pics = [s for s in probe.streams if s.attached_pic]
    assert len(pics) == 1
    assert 0 < pics[0].picture_bytes < 2 * 1024 * 1024
    assert check_audio(probe, min_s=15, max_s=600) is None
    out = tmp_path / "canonical.flac"
    canonicalize(ffmpeg_tools, src, "mp3", out)
    flac = probe_audio(ffmpeg_tools, out, "flac")
    assert [s.codec_type for s in flac.streams] == ["audio"]


@pytest.mark.ffmpeg
def test_a_real_video_stream_is_flagged(ffmpeg_tools: Tools, tmp_path: Path) -> None:
    src = media.mp4_with_video(ffmpeg_tools, tmp_path)
    probe = probe_audio(ffmpeg_tools, src, sniff(src.read_bytes()[:16]).fmt)
    assert any(s.codec_type == "video" and not s.attached_pic for s in probe.streams)
    assert check_audio(probe, min_s=15, max_s=600) is not None


@pytest.mark.ffmpeg
def test_codec_labels_of_real_files(ffmpeg_tools: Tools, tmp_path: Path) -> None:
    cases = {
        "a.m4a": (["-c:a", "aac"], "aac_lc"),
        "a.mp3": (["-c:a", "libmp3lame"], "mp3"),
        "a.flac": (["-c:a", "flac"], "flac"),
        "a.ogg": (["-c:a", "libvorbis"], "vorbis"),
    }
    for name, (args, label) in cases.items():
        path = media.encode(ffmpeg_tools, tmp_path, name, *args)
        fmt = sniff(path.read_bytes()[:16]).fmt
        audio = first_audio(probe_audio(ffmpeg_tools, path, fmt))
        assert audio is not None
        assert codec_label(audio) == label, name


@pytest.mark.ffmpeg
def test_raw_adts_aac_is_not_a_song(ffmpeg_tools: Tools, tmp_path: Path) -> None:
    path = media.encode(ffmpeg_tools, tmp_path, "raw.aac", "-c:a", "aac", "-f", "adts")
    assert path.read_bytes()[0] == 0xFF  # a real ADTS header: sync bits set
    with pytest.raises(NotSniffable):
        sniff(path.read_bytes()[:16])


@pytest.mark.ffmpeg
def test_a_truncated_wav_is_not_accepted_silently(ffmpeg_tools: Tools, tmp_path: Path) -> None:
    src = tmp_path / "in.wav"
    click_track(src, duration=20)
    cut = tmp_path / "cut.wav"
    cut.write_bytes(src.read_bytes()[: 44 + 4000])  # the header still declares 20 s
    probe = probe_audio(ffmpeg_tools, cut, "wav")
    if check_audio(probe, min_s=15, max_s=600) is None:  # the header's claim got through the probe
        with pytest.raises(DecodeFailed):
            canonicalize(ffmpeg_tools, cut, "wav", tmp_path / "out.flac")
        assert not (tmp_path / "out.flac").exists()


@pytest.mark.ffmpeg
def test_a_playlist_renamed_mp3_opens_no_connection(ffmpeg_tools: Tools, tmp_path: Path) -> None:
    """G0-25 pattern: an HLS playlist pointing at a local listener; the listener sees nothing."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(5)
    listener.settimeout(0.2)
    port = listener.getsockname()[1]
    connections: list[object] = []
    stop = threading.Event()

    def accept() -> None:
        while not stop.is_set():
            try:
                connections.append(listener.accept())
            except OSError:
                continue

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    playlist = tmp_path / "evil.mp3"
    playlist.write_text(
        f"#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:10\n#EXTINF:10,\n"
        f"http://127.0.0.1:{port}/seg0.ts\n#EXT-X-ENDLIST\n"
    )
    try:
        with pytest.raises(NotSniffable):
            sniff(playlist.read_bytes()[:16])
        # even if the sniff were bypassed, the forced demuxer and the whitelist keep it local
        with contextlib.suppress(FfError):
            probe_audio(ffmpeg_tools, playlist, "mp3")
        with pytest.raises(FfError):
            canonicalize(ffmpeg_tools, playlist, "hls", tmp_path / "o.flac")
    finally:
        time.sleep(0.3)
        stop.set()
        thread.join(2)
        listener.close()
    assert connections == []

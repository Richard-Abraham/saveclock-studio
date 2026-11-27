"""Hostile media (plan 008, T-2.14): a corpus of at least 60 generated files, at two layers.

Layer A, through the API and a real worker: every file reaches a documented outcome, the worker
survives, nothing is written outside the blob root and the scratch directory, and nothing leaks.
Layer B, straight at the adapters with the production FFmpeg template, for every forced format: a
listener on 127.0.0.1 must see no connection. A negative control that SHOULD hit the listener
proves the detector can see a leak (a gate that cannot fail proves nothing).
"""

import asyncio
import importlib.util
import json
import os
import socketserver
import subprocess
import threading
import time
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx
import pytest

from saveclock.adapters.ffmpeg import FfError, Tools, canonicalize, probe_audio
from saveclock.domain.audio_rules import FileRejectReason
from saveclock.domain.media_sniff import ALLOWED_EXT
from tests.integration.conftest import Harness
from tests.integration.housekeeping_harness import Hk

pytestmark = [pytest.mark.security, pytest.mark.integration, pytest.mark.ffmpeg]
ROOT = Path(__file__).resolve().parents[4]
LEAK_TOKEN = "root:x:"  # noqa: S105 - a short /etc/passwd token; only a boolean is kept, never the content
SETTLED_OK = {"rejected", "failed_analysis", "planning", "draft_ready", "failed_plan"}
# files the magic-byte sniff must refuse before FFmpeg starts (raw ADTS AAC is not accepted)
REFUSED_BY_SNIFF = {
    "adts_aac", "hls_playlist", "concat", "text_protocol", "renamed_binary", "zero_byte",
}  # fmt: skip
IN_FLIGHT = {"created", "uploading", "validating", "analyzing"}
HTTP_OUTCOMES = {202, 400, 413, 415, 422}
REJECT_REASONS = {r.value for r in FileRejectReason}
WORKER_SETTLE_S = 90


def load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "make_hostile_corpus", ROOT / "eval" / "scripts" / "make_hostile_corpus.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Listener:
    """Records inbound TCP connections on 127.0.0.1 (an ephemeral port)."""

    def __init__(self) -> None:
        outer = self
        self.count = 0

        class Handler(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                outer.count += 1
                try:
                    self.request.settimeout(0.5)
                    self.request.recv(1024)
                    self.request.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
                except OSError:
                    pass

        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port: int = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def listener() -> Any:
    found = Listener()
    yield found
    found.close()


def corpus(tmp_path: Path, port: int, tools: Tools) -> tuple[Path, list[dict[str, Any]]]:
    out = tmp_path / "hostile"
    entries = load_generator().generate(out, port=port, ffmpeg_bin=tools.ffmpeg)
    assert len(entries) >= 60
    categories: dict[str, int] = {}
    for e in entries:
        categories[e["category"]] = categories.get(e["category"], 0) + 1
    assert min(categories.values()) >= 3, categories  # every category has at least three files
    return out, entries


def listdir_names(path: Path) -> set[str]:
    return {p.name for p in path.iterdir()}


def incoming_files(blob_root: Path, project: str) -> list[Path]:
    return list((blob_root / "songs" / project).glob("incoming.bin*"))


def final_state(scratch: Path, top: Path, before: set[str]) -> tuple[list[Path], set[str], str]:
    """Scratch leftovers, new top-level names, and the worker logs (all blocking reads)."""
    leftovers = list(scratch.iterdir()) if scratch.exists() else []
    appeared = listdir_names(top) - before
    log = "".join(p.read_text(errors="replace") for p in top.glob("worker*.log"))
    return leftovers, appeared, log


def descendants(pid: int) -> set[int]:
    """Every process below `pid` (a crash loop would show as new pids)."""
    parents: dict[int, int] = {}
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            try:
                stat = (entry / "stat").read_text()
                parents[int(entry.name)] = int(stat.rsplit(")", 1)[1].split()[1])
            except (OSError, ValueError, IndexError):
                continue
    found: set[int] = set()
    frontier = {pid}
    while frontier:
        children = {p for p, parent in parents.items() if parent in frontier} - found
        found |= children
        frontier = children
    return found


async def settle(hk: Hk, project_id: str) -> tuple[str, str | None]:
    """The project's (status, status_reason) once the worker is done with it."""
    deadline = time.monotonic() + WORKER_SETTLE_S
    status = ""
    while time.monotonic() < deadline:
        row = (
            await hk.sql("SELECT status, status_reason FROM projects WHERE id=$1", UUID(project_id))
        )[0]
        status = str(row[0])
        if status not in IN_FLIGHT:
            return status, row[1]
        await asyncio.sleep(0.4)
    msg = f"{project_id} did not settle in {WORKER_SETTLE_S} s (last: {status})"
    raise AssertionError(msg)


async def test_layer_a_every_file_reaches_a_documented_outcome(  # noqa: PLR0917
    harness: Harness,
    hk: Hk,
    api_client: httpx.AsyncClient,
    listener: Listener,
    ffmpeg_tools: Tools,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out, entries = corpus(tmp_path, listener.port, ffmpeg_tools)
    worker = harness.start_worker(["analysis", "render"])
    scratch = harness.tmp_path / "scratch"
    top_before = await asyncio.to_thread(listdir_names, tmp_path)  # canary: nothing else appears
    boot_deadline = time.monotonic() + 30  # the worker boots and registers: poll, never guess
    before = descendants(worker.pid)
    while not before and time.monotonic() < boot_deadline:
        await asyncio.sleep(0.5)
        before = descendants(worker.pid)
    assert before, "the worker has no child processes: is it running?"

    accepted: list[tuple[str, str]] = []
    bodies: list[str] = []
    for entry in entries:
        data = (out / entry["path"]).read_bytes()
        project = (await api_client.post("/api/v1/projects", json={})).json()["id"]
        response = await api_client.post(
            f"/api/v1/projects/{project}/song",
            content=data,
            headers={
                "content-type": entry["content_type"],
                "x-filename": quote(entry["upload_name"], safe=""),
            },
        )
        bodies.append(response.text)
        assert response.status_code in HTTP_OUTCOMES, (entry["path"], response.status_code)
        if entry["category"] in REFUSED_BY_SNIFF:  # never reaches FFmpeg: 415 unsupported_media
            assert response.status_code == 415, (entry["path"], response.status_code)
        if response.status_code == 202:
            accepted.append((entry["path"], project))
    outcomes: dict[str, str] = {}
    for name, project in accepted:
        status, reason = await settle(hk, project)
        assert status in SETTLED_OK, (name, status)
        outcomes[name] = status
        body = (await api_client.get(f"/api/v1/projects/{project}")).json()
        bodies.append(json_text(body))
        if status == "rejected":
            assert reason in REJECT_REASONS, (name, reason)
            left = await asyncio.to_thread(incoming_files, harness.blob_root, project)
            assert not left, f"{name}: upload left behind"

    after = descendants(worker.pid)
    assert worker.poll() is None, "the worker exited"
    assert after == before, f"worker processes changed (a crash loop?): {before} -> {after}"
    leftovers, appeared, log = await asyncio.to_thread(final_state, scratch, tmp_path, top_before)
    assert not leftovers, "scratch was not cleaned"
    assert all(n == "scratch" or n.startswith("worker") for n in appeared), appeared
    assert LEAK_TOKEN not in log
    assert all(LEAK_TOKEN not in b for b in bodies)
    assert listener.count == 0, "a hostile file made FFmpeg open a connection"
    with capsys.disabled():
        print(f"\nhostile files: {len(entries)}")
        print(f"settled outcomes: {len(outcomes)} of {len(accepted)} accepted")
        print(f"connections: {listener.count}")


def json_text(body: Any) -> str:
    return json.dumps(body)


def ffmpeg_raw(cmd: list[str]) -> tuple[int, str]:
    """Deliberately not `adapters.ffmpeg.run`: the control needs a template the wrapper refuses."""
    done = subprocess.run(  # noqa: S603 - fixed argument list, no shell
        cmd, capture_output=True, timeout=60, check=False, env={"PATH": os.environ["PATH"]}
    )
    return done.returncode, (done.stdout + done.stderr).decode("utf-8", "replace")


def test_layer_b_the_production_template_never_connects(
    listener: Listener,
    ffmpeg_tools: Tools,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out, entries = corpus(tmp_path, listener.port, ffmpeg_tools)
    leaked = False
    runs = 0
    for entry in entries:
        path = out / entry["path"]
        for fmt in ALLOWED_EXT:
            runs += 1
            try:
                probe_audio(ffmpeg_tools, path, fmt)
            except FfError as exc:
                leaked = leaked or LEAK_TOKEN in str(exc)
            try:
                canonicalize(ffmpeg_tools, path, fmt, tmp_path / "out.flac", timeout=30)
            except FfError as exc:
                leaked = leaked or LEAK_TOKEN in str(exc)
            (tmp_path / "out.flac").unlink(missing_ok=True)
    assert listener.count == 0, "the production template opened a connection"
    assert not leaked, "an output contained a token of /etc/passwd"
    with capsys.disabled():
        print(f"\nhostile files: {len(entries)}")
        print(f"adapter runs: {runs}")
        print(f"connections: {listener.count}")


def test_the_negative_control_hits_the_listener(
    listener: Listener, ffmpeg_tools: Tools, tmp_path: Path
) -> None:
    """The same HLS playlist with an explicit permissive whitelist and a forced `-f hls` (built by
    the test itself: the adapter refuses caller-supplied protocol options) MUST reach the
    listener. If it does not, the detector is blind and every "0 connections" means nothing."""
    out, _ = corpus(tmp_path, listener.port, ffmpeg_tools)
    playlist = out / "hls_http_0.wav"
    ffmpeg_raw(
        [
            ffmpeg_tools.ffprobe, "-v", "error", "-protocol_whitelist", "file,http,https,tcp",
            "-f", "hls", str(playlist),
        ]
    )  # fmt: skip
    deadline = time.monotonic() + 5
    while listener.count == 0 and time.monotonic() < deadline:
        time.sleep(0.1)
    assert listener.count >= 1, "the detector does not work: the control made no connection"

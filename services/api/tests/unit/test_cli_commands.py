# ruff: noqa: E501  (the fake API payloads are kept on one line each, for reading)
"""Each command issues exactly the calls of the ARCH §2 mapping, by operation, in order."""

import json
import tracemalloc
from pathlib import Path
from typing import Any

import httpx
import pytest

from saveclock.cli import main as cli_main
from saveclock.cli.client import Client
from tests.unit.cli_fakes import (
    PID,
    RID,
    CliRun,
    Fake,
    analysis,
    err,
    j,
    parsed,
    plan,
    project,
)  # fmt: skip

P = f"/projects/{PID}"


def _sse(*events: tuple[str, dict[str, Any]]) -> httpx.Response:
    body = "retry: 3000\n\n" + "".join(f"event: {n}\ndata: {json.dumps(d)}\n\n" for n, d in events)
    return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})


@pytest.mark.unit
def test_new_creates_then_uploads_and_prints_the_id(cli_run: CliRun, tmp_path: Path) -> None:
    song = tmp_path / "a song.mp3"
    song.write_bytes(b"abc" * 100)
    fake = (
        Fake()
        .on("POST", "/projects", j(201, {"id": PID}))
        .on("POST", f"{P}/song", j(202, {"job_id": RID, "ui_status": "analysing"}))
    )
    code, out, _ = cli_run(
        fake, "new", str(song), "--vibe", "calm", "--keywords", "a b,c d", "--duration", "30"
    )
    assert code == 0
    assert out.strip() == f"project {PID}"
    assert fake.ops == ["POST /projects", f"POST {P}/song"]
    assert json.loads(fake.requests[0].content) == {
        "options": {"vibe": "calm", "keywords_override": ["a b", "c d"], "duration": 30}
    }
    up = fake.requests[1]
    assert up.headers["content-length"] == "300"
    assert up.headers["x-filename"] == "a%20song.mp3"
    assert up.headers["content-type"] == "application/octet-stream"
    assert up.content == b"abc" * 100


@pytest.mark.unit
def test_new_sends_an_overlong_vibe_as_is_the_api_decides(cli_run: CliRun, tmp_path: Path) -> None:
    song = tmp_path / "s.mp3"
    song.write_bytes(b"x")
    fake = Fake().on("POST", "/projects", err(422, "validation_error"))
    code, _o, errout = cli_run(fake, "new", str(song), "--vibe", "v" * 300)
    assert code == 1
    assert "validation_error" in errout
    assert json.loads(fake.requests[0].content)["options"]["vibe"] == "v" * 300


@pytest.mark.unit
def test_a_failed_upload_still_names_the_project(cli_run: CliRun, tmp_path: Path) -> None:
    song = tmp_path / "s.mp3"
    song.write_bytes(b"x")
    fake = (
        Fake()
        .on("POST", "/projects", j(201, {"id": PID}))
        .on("POST", f"{P}/song", err(422, "file_rejected", reason="too_short"))
    )
    code, _o, errout = cli_run(fake, "new", str(song))
    assert code == 1
    assert f"project_id={PID}" in errout


class _Lazy(httpx.BaseTransport):
    """Consumes an upload chunk by chunk like a server (MockTransport would buffer it whole)."""

    def __init__(self, fake: Fake) -> None:
        self.fake, self.seen = fake, 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/song"):
            self.fake.requests.append(request)
            for chunk in request.stream:  # type: ignore[union-attr]
                self.seen += len(chunk)
            return j(202, {"job_id": RID, "ui_status": "analysing"})
        return self.fake.handler(request)


@pytest.mark.unit
def test_new_streams_the_song_instead_of_reading_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    song = tmp_path / "big.wav"
    with song.open("wb") as fh:
        fh.truncate(50 * 1024 * 1024)  # a sparse 50 MB file
    fake = Fake().on("POST", "/projects", j(201, {"id": PID}))
    lazy = _Lazy(fake)
    monkeypatch.setattr(cli_main, "Client", lambda url: Client(url, transport=lazy))
    tracemalloc.start()
    before = tracemalloc.get_traced_memory()[0]
    code = cli_main.main(["new", str(song)])
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert code == 0
    assert lazy.seen == 50 * 1024 * 1024
    assert peak - before < 10 * 1024 * 1024


@pytest.mark.unit
def test_show_calls_project_analysis_plan_and_merges(cli_run: CliRun) -> None:
    fake = (
        Fake()
        .on("GET", P, j(200, project()))
        .on("GET", f"{P}/analysis", j(200, analysis()))
        .on("GET", f"{P}/plan", j(200, plan()))
    )
    code, out, _ = cli_run(fake, "show", PID, "--json")
    assert code == 0
    assert fake.ops == [f"GET {P}", f"GET {P}/analysis", f"GET {P}/plan"]
    doc = parsed(out)
    assert doc["analysis"]["n_beats"] == 3
    assert doc["keywords"] == {"source": "table", "override": None}
    assert doc["plan"]["n_cuts"] == 2


@pytest.mark.unit
def test_show_skips_analysis_and_plan_when_the_project_has_none(cli_run: CliRun) -> None:
    fake = Fake().on("GET", P, j(200, project("analysing", analysis=None, plan=None)))
    code, out, _ = cli_run(fake, "show", PID, "--json")
    assert code == 0
    assert fake.ops == [f"GET {P}"]
    assert parsed(out)["analysis"] is None


@pytest.mark.unit
def test_keywords_set_reads_the_plan_then_patches_and_waits_for_the_new_version(
    cli_run: CliRun, cli_clock: list[float]
) -> None:
    fake = (
        Fake()
        .on("GET", f"{P}/plan", j(200, plan(3)))
        .on("PATCH", f"{P}/plan", j(202, {"job_id": RID}))
        .on(
            "GET", P,
            j(200, project("analysing")),
            j(200, project("draft", plan={"version": 4, "frozen": False, "total_frames": 9, "n_cuts": 2, "keyword_source": "explicit"})),
        )
    )  # fmt: skip
    code, out, _ = cli_run(fake, "keywords", "set", PID, "night drive", "city", "--json")
    assert code == 0
    assert fake.ops == [f"GET {P}/plan", f"PATCH {P}/plan", f"GET {P}", f"GET {P}"]
    assert json.loads(fake.requests[1].content) == {
        "base_version": 3,
        "ops": [{"op": "set_keywords", "keywords": ["night drive", "city"]}],
    }
    doc = parsed(out)
    assert (doc["applied"], doc["plan_version"], doc["keyword_source"]) == (True, 4, "explicit")
    assert cli_clock == [1.0]


@pytest.mark.unit
def test_keywords_set_retries_once_after_a_version_conflict(
    cli_run: CliRun, cli_clock: list[float]
) -> None:
    fake = (
        Fake()
        .on("GET", f"{P}/plan", j(200, plan(1)), j(200, plan(2)))
        .on(
            "PATCH", f"{P}/plan",
            err(409, "plan_version_conflict", current_version=2),
            j(202, {"job_id": RID}),
        )
        .on("GET", P, j(200, project("draft", plan={"version": 3, "frozen": False, "total_frames": 9, "n_cuts": 2, "keyword_source": "explicit"})))
    )  # fmt: skip
    code, _o, _e = cli_run(fake, "keywords", "set", PID, "city")
    assert code == 0
    assert fake.ops[:4] == [f"GET {P}/plan", f"PATCH {P}/plan", f"GET {P}/plan", f"PATCH {P}/plan"]
    assert json.loads(fake.requests[3].content)["base_version"] == 2


@pytest.mark.unit
def test_keywords_set_succeeds_when_an_unfrozen_plan_was_replaced_in_place(
    cli_run: CliRun, cli_clock: list[float]
) -> None:
    same = {
        "version": 3,
        "frozen": False,
        "total_frames": 9,
        "n_cuts": 2,
        "keyword_source": "explicit",
    }
    fake = (
        Fake()
        .on("GET", f"{P}/plan", j(200, plan(3)))
        .on("PATCH", f"{P}/plan", j(202, {"job_id": RID}))
        .on("GET", P, j(200, project("draft", plan=same)))
    )
    code, out, _ = cli_run(fake, "keywords", "set", PID, "city", "--json")
    assert code == 0
    assert (parsed(out)["applied"], parsed(out)["plan_version"]) == (True, 3)


@pytest.mark.unit
def test_keywords_set_is_a_failure_when_the_draft_comes_back_with_a_reason(
    cli_run: CliRun, cli_clock: list[float]
) -> None:
    old = {"version": 3, "frozen": False, "total_frames": 9, "n_cuts": 2, "keyword_source": "table"}
    fake = (
        Fake()
        .on("GET", f"{P}/plan", j(200, plan(3)))
        .on("PATCH", f"{P}/plan", j(202, {"job_id": RID}))
        .on("GET", P, j(200, project("draft", plan=old, status_reason="stock_unavailable")))
    )
    code, _o, errout = cli_run(fake, "keywords", "set", PID, "city")
    assert code == 1
    assert "keywords not applied, previous plan kept" in errout
    assert "stock_unavailable" in errout


@pytest.mark.unit
def test_keywords_set_no_wait_returns_after_the_202(cli_run: CliRun) -> None:
    fake = (
        Fake()
        .on("GET", f"{P}/plan", j(200, plan(1)))
        .on("PATCH", f"{P}/plan", j(202, {"job_id": RID}))
    )
    code, out, _ = cli_run(fake, "keywords", "set", PID, "city", "--no-wait")
    assert code == 0
    assert RID in out
    assert fake.ops == [f"GET {P}/plan", f"PATCH {P}/plan"]


@pytest.mark.unit
@pytest.mark.parametrize("reason", ["wrong_state", "job_active", "render_active"])
def test_keywords_set_shows_a_conflict_and_never_retries_it(cli_run: CliRun, reason: str) -> None:
    fake = (
        Fake()
        .on("GET", f"{P}/plan", j(200, plan(1)))
        .on("PATCH", f"{P}/plan", err(409, "conflict", reason=reason))
    )
    code, _o, errout = cli_run(fake, "keywords", "set", PID, "city")
    assert code == 1
    assert f"reason={reason}" in errout
    assert fake.ops.count(f"PATCH {P}/plan") == 1


@pytest.mark.unit
def test_plan_calls_get_plan_only(cli_run: CliRun) -> None:
    fake = Fake().on("GET", f"{P}/plan", j(200, plan()))
    code, out, _ = cli_run(fake, "plan", PID, "--json")
    assert code == 0
    assert fake.ops == [f"GET {P}/plan"]
    assert "secret" not in out  # the mezzanine key is a storage path: never printed


@pytest.mark.unit
def test_render_creates_then_polls_until_ready(cli_run: CliRun, cli_clock: list[float]) -> None:
    verify = {
        "passed": True,
        "blocks": 0,
        "warns": 1,
        "failed": [],
        "render_ms": 9000,
        "verify_ms": 9500,
    }
    ready = {"state": "ready", "plan_version": 2, "error_code": None, "verify": verify}
    fake = (
        Fake()
        .on("POST", f"{P}/renders", j(202, {"render_id": RID}))
        .on("GET", f"/renders/{RID}", j(200, {**ready, "state": "running", "verify": None}), j(200, ready))
    )  # fmt: skip
    code, out, _ = cli_run(fake, "render", PID, "--plan-version", "2")
    assert code == 0
    assert fake.ops == [f"POST {P}/renders", f"GET /renders/{RID}", f"GET /renders/{RID}"]
    assert json.loads(fake.requests[0].content) == {"plan_version": 2}
    assert f"render {RID} ready" in out


@pytest.mark.unit
def test_render_failure_exits_1_with_the_error_code(
    cli_run: CliRun, cli_clock: list[float]
) -> None:
    fake = (
        Fake()
        .on("POST", f"{P}/renders", j(202, {"render_id": RID}))
        .on("GET", f"/renders/{RID}", j(200, {"state": "failed", "plan_version": 1, "error_code": "verification_failed", "verify": None}))
    )  # fmt: skip
    code, out, _ = cli_run(fake, "render", PID)
    assert code == 1
    assert "verification_failed" in out


def _export_fake(tmp: Path) -> Fake:
    def download(kind: str) -> httpx.Response:
        return httpx.Response(
            200, content=f"data-{kind}".encode(),
            headers={"content-disposition": f'attachment; filename="clip-{kind}.mp4"'},
        )  # fmt: skip

    return (
        Fake()
        .on("GET", P, j(200, project("ready", render={"id": RID, "state": "ready", "mode_a_state": None})))
        .on("POST", f"/renders/{RID}/mode-a", j(202, {"render_id": RID, "mode_a_state": "queued"}))
        .on("GET", f"/renders/{RID}", j(200, {"mode_a_state": "running"}), j(200, {"mode_a_state": "ready"}))
        .on("GET", f"/renders/{RID}/download", lambda r: download(r.url.params["kind"]))
        .on("GET", f"{P}/credits", j(200, {"items": [], "text": "Footage: test"}))
    )  # fmt: skip


@pytest.mark.unit
def test_export_a_requests_mode_a_polls_and_downloads_with_song(
    cli_run: CliRun, cli_clock: list[float], tmp_path: Path
) -> None:
    fake = _export_fake(tmp_path)
    code, out, _ = cli_run(fake, "export", PID, "--mode", "a", "--out", str(tmp_path), "--json")
    assert code == 0
    assert fake.ops == [
        f"GET {P}", f"POST /renders/{RID}/mode-a", f"GET /renders/{RID}", f"GET /renders/{RID}",
        f"GET /renders/{RID}/download",
    ]  # fmt: skip
    assert fake.requests[-1].url.params["kind"] == "with_song"
    assert (tmp_path / "clip-with_song.mp4").read_bytes() == b"data-with_song"
    assert parsed(out)["files"][0]["kind"] == "with_song"


@pytest.mark.unit
def test_export_b_downloads_three_files_then_prints_the_credits(
    cli_run: CliRun, tmp_path: Path
) -> None:
    fake = _export_fake(tmp_path)
    code, out, _ = cli_run(fake, "export", PID, "--mode", "b", "--out", str(tmp_path))
    assert code == 0
    assert fake.ops == [f"GET {P}"] + [f"GET /renders/{RID}/download"] * 3 + [f"GET {P}/credits"]
    assert [r.url.params["kind"] for r in fake.requests[1:4]] == [
        "silent_video",
        "cutlist_json",
        "cutlist_csv",
    ]
    assert "Footage: test" in out


@pytest.mark.unit
def test_export_refuses_a_render_that_is_not_ready_and_calls_nothing_else(
    cli_run: CliRun, tmp_path: Path
) -> None:
    for render in (None, {"id": RID, "state": "running", "mode_a_state": None}):
        fake = Fake().on("GET", P, j(200, project("rendering", render=render)))
        code, _o, errout = cli_run(fake, "export", PID, "--mode", "b", "--out", str(tmp_path))
        assert code == 1
        assert "conflict" in errout
        assert fake.ops == [f"GET {P}"]


@pytest.mark.unit
def test_export_needs_an_existing_directory(cli_run: CliRun, tmp_path: Path) -> None:
    fake = Fake()
    code, _o, errout = cli_run(fake, "export", PID, "--mode", "b", "--out", str(tmp_path / "nope"))
    assert code == 2
    assert "does not exist" in errout
    assert fake.requests == []


@pytest.mark.unit
def test_status_without_an_id_lists_projects(cli_run: CliRun) -> None:
    items = [{"id": PID, "title": "t", "ui_status": "draft", "disk_bytes": 1,
              "last_activity_at": "x", "created_at": "x"}]  # fmt: skip
    fake = Fake().on("GET", "/projects", j(200, {"items": items, "next_cursor": None}))
    code, out, _ = cli_run(fake, "status")
    assert code == 0
    assert fake.ops == ["GET /projects"]
    assert PID in out


@pytest.mark.unit
def test_status_watch_stops_on_draft_ready(cli_run: CliRun, cli_clock: list[float]) -> None:
    fake = (
        Fake()
        .on("GET", f"{P}/events", _sse(
            ("state", {"status": "x", "ui_status": "analysing", "flags": {}}),
            ("progress", {"step": "analyse", "pct": 40, "message_key": "k"}),
            ("draft_ready", {"version": 1}),
        ))
        .on("GET", P, j(200, project("draft")))
    )  # fmt: skip
    code, out, errout = cli_run(fake, "status", PID, "--watch")
    assert code == 0
    assert "analyse: 40%" in errout
    assert fake.ops == [f"GET {P}/events", f"GET {P}"]
    assert "draft" in out


@pytest.mark.unit
def test_status_watch_stops_on_a_draft_snapshot(cli_run: CliRun, cli_clock: list[float]) -> None:
    fake = (
        Fake()
        .on(
            "GET",
            f"{P}/events",
            _sse(("state", {"status": "x", "ui_status": "draft", "flags": {}})),
        )
        .on("GET", P, j(200, project("draft")))
    )
    code, _o, _e = cli_run(fake, "status", PID, "--watch")
    assert code == 0
    assert fake.ops.count(f"GET {P}/events") == 1


@pytest.mark.unit
def test_status_watch_exits_1_on_a_failed_event(cli_run: CliRun, cli_clock: list[float]) -> None:
    fake = (
        Fake()
        .on("GET", f"{P}/events", _sse(("failed", {"stage": "draft", "code": "stock_unavailable", "retryable": True})))
        .on("GET", P, j(200, project("failed", status_reason="stock_unavailable")))
    )  # fmt: skip
    code, out, errout = cli_run(fake, "status", PID, "--watch")
    assert code == 1
    assert "stock_unavailable" in out + errout


@pytest.mark.unit
def test_status_watch_reconnects_after_a_closed_stream(
    cli_run: CliRun, cli_clock: list[float]
) -> None:
    fake = (
        Fake()
        .on(
            "GET", f"{P}/events",
            _sse(("state", {"status": "x", "ui_status": "analysing", "flags": {}})),
            _sse(("state", {"status": "x", "ui_status": "draft", "flags": {}})),
        )
        .on("GET", P, j(200, project("draft")))
    )  # fmt: skip
    code, _o, _e = cli_run(fake, "status", PID, "--watch")
    assert code == 0
    assert fake.ops.count(f"GET {P}/events") == 2


@pytest.mark.unit
def test_status_watch_falls_back_to_polling_on_too_many_streams(
    cli_run: CliRun, cli_clock: list[float]
) -> None:
    fake = (
        Fake()
        .on("GET", f"{P}/events", err(409, "conflict", reason="too_many_streams"))
        .on("GET", P, j(200, project("analysing")), j(200, project("draft")))
    )
    code, _o, _e = cli_run(fake, "status", PID, "--watch")
    assert code == 0
    assert fake.ops[0] == f"GET {P}/events"
    assert fake.ops.count(f"GET {P}") >= 2


@pytest.mark.unit
def test_open_makes_no_request(cli_run: CliRun, monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []

    def fake_open(url: str) -> bool:
        opened.append(url)
        return True

    monkeypatch.setattr("saveclock.cli.commands.webbrowser.open", fake_open)
    fake = Fake()
    code, out, _ = cli_run(fake, "open", PID)
    assert code == 0
    assert fake.requests == []
    assert opened == [f"http://localhost:3000/projects/{PID}"]
    assert out.strip() == opened[0]

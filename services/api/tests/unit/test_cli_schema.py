"""Every `--json` output validates against its schema; `show` stays a summary (SEC-169)."""

import json
from pathlib import Path
from typing import Any

import pytest

from saveclock.cli import schema
from tests.unit.cli_fakes import PID, RID, CliRun, Fake, analysis, err, j, parsed, plan, project

ROOT = Path(__file__).resolve().parents[4]
P = f"/projects/{PID}"
FORBIDDEN_KEYS = {
    "energy_curve",
    "waveform_peaks",
    "beats_s",
    "downbeats_s",
    "original_filename",
    "mezzanine_key",
}


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


def _validate(command: str, doc: Any) -> None:
    model = schema.OUTPUTS[command]
    model.model_validate(doc)  # the generated file is checked against the model by contracts-check
    stored = json.loads(
        (ROOT / "packages/contracts/schemas" / f"saveclock-{command}.v1.schema.json").read_text()
    )
    assert stored == model.model_json_schema()


@pytest.mark.unit
def test_show_is_a_summary_with_no_audio_waveform_beats_or_filename(cli_run: CliRun) -> None:
    fake = (
        Fake()
        .on("GET", P, j(200, project()))
        .on("GET", f"{P}/analysis", j(200, analysis()))
        .on("GET", f"{P}/plan", j(200, plan()))
    )
    _code, out, _ = cli_run(fake, "show", PID, "--json")
    doc = parsed(out)
    assert not _keys(doc) & FORBIDDEN_KEYS
    assert "secret-name" not in out
    assert set(doc) == {
        "schema_version",
        "project",
        "song",
        "analysis",
        "keywords",
        "plan",
        "render",
    }
    assert set(doc["analysis"]) == {
        "tempo_bpm", "tempo_octave_adjust", "confidence", "fallback", "n_beats", "n_downbeats",
        "sections", "segment", "low_confidence_ranges",
    }  # fmt: skip
    assert set(doc["song"]) == {"duration_s", "codec", "sample_rate", "channels"}
    _validate("show", doc)


@pytest.mark.unit
def test_an_unknown_extra_key_fails_validation() -> None:
    doc = {"schema_version": "1", "url": "u", "opened": True, "extra": 1}
    with pytest.raises(ValueError, match="extra"):
        schema.OpenOut.model_validate(doc)


@pytest.mark.unit
def test_every_command_json_output_validates_against_its_schema(
    cli_run: CliRun, cli_clock: list[float], tmp_path: Path
) -> None:
    song = tmp_path / "s.mp3"
    song.write_bytes(b"x")
    done = {
        "version": 2,
        "frozen": False,
        "total_frames": 9,
        "n_cuts": 2,
        "keyword_source": "explicit",
    }
    ready = {
        "state": "ready",
        "plan_version": 1,
        "error_code": None,
        "mode_a_state": "ready",
        "verify": None,
    }
    fake = (
        Fake()
        .on("POST", "/projects", j(201, {"id": PID}))
        .on("POST", f"{P}/song", j(202, {"job_id": RID, "ui_status": "analysing"}))
        .on("GET", P, j(200, project("draft", plan=done)))
        .on("GET", f"{P}/plan", j(200, plan(1)))
        .on("PATCH", f"{P}/plan", j(202, {"job_id": RID}))
        .on("POST", f"{P}/renders", j(202, {"render_id": RID}))
        .on("GET", f"/renders/{RID}", j(200, ready))
        .on("GET", "/projects", j(200, {"items": [], "next_cursor": None}))
    )
    for command, argv in {
        "new": ["new", str(song)],
        "keywords": ["keywords", "set", PID, "city"],
        "plan": ["plan", PID],
        "render": ["render", PID],
        "status": ["status", PID],
    }.items():
        code, out, _ = cli_run(fake, *argv, "--json")
        assert code == 0, (command, out)
        _validate(command, parsed(out))
    _code, out, _ = cli_run(fake, "status", "--json")
    _validate("status", parsed(out))


@pytest.mark.unit
def test_an_error_prints_the_error_document_in_json_mode(cli_run: CliRun) -> None:
    fake = Fake().on("GET", P, err(404, "not_found"))
    code, out, _ = cli_run(fake, "status", PID, "--json")
    assert code == 1
    doc = parsed(out)
    assert doc["error"]["code"] == "not_found"
    _validate("error", doc)

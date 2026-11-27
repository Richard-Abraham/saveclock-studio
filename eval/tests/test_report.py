"""The results table, the soak counters and the review sheets (plan 009, Step 7)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

from saveclock_eval import report, sheets

FACTS = {"cpu_count": 4, "tuning": {"ffmpeg_threads": 4}, "anthropic_configured": False}


def rec(i: int, outcome: str = "completed", code: str | None = None, **over: Any) -> dict[str, Any]:
    base = {
        "index": i, "outcome": outcome, "error_code": code, "project_id": f"p{i}", "render_id": f"r{i}",
        "song_label": f"song-{i}", "tempo_bpm": 128.0, "keywords": ["night", "city"], "keyword_source": "table",
        "timings": {"analysis_s": 5.0, "draft_s": 30.0, "render_ms": 20000, "verify_ms": 21000, "mode_a_s": 2.0},
        "verify": {"passed": True, "blocks": 0, "warns": 0, "failed": []}, "mode_a": True,
        "checks": [{"id": "QM-038", "ok": True, "detail": ""}],
        "cuts": [{"index": k, "start_s": k * 0.5, "end_s": k * 0.5 + 0.5} for k in range(4)],
        "master_path": None, "confidence": 0.9, "n_sections": 3, "beat": None, "alignment": None,
    }  # fmt: skip
    return {**base, **over}


def test_the_status_vocabulary_is_closed() -> None:
    for ok in ("PASS", "FAIL", "FAIL (hardware differs: 3 CPUs)", "NOT MEASURED (why)", "PENDING (what)", "OWNER-BLOCKED (soak)"):
        assert report.status_word(ok) is not None
    for bad in ("OK", "passed", "PASSING", "pass", "FAILED", "PASS-ish", ""):
        assert report.status_word(bad) is None


def test_every_row_of_a_run_is_in_the_vocabulary() -> None:
    rows = report.build_rows([rec(i) for i in range(3)], FACTS)
    assert rows
    assert all(report.status_word(r.status) for r in rows), [r.status for r in rows if not report.status_word(r.status)]


def test_a_not_measured_row_never_becomes_pass() -> None:
    rows = {r.id: r for r in report.build_rows([rec(i) for i in range(3)], FACTS)}
    for qm in ("QM-001", "QM-003", "QM-004", "QM-010", "QM-016"):
        assert rows[qm].status.startswith("NOT MEASURED (no golden set")
    assert rows["QM-083"].status.startswith("NOT MEASURED")
    assert rows["QM-069"].status.startswith("PENDING")
    # three renders can never make a soak row PASS, even when every one of them is clean
    for qm in ("QM-060", "QM-064", "QM-087", "QM-038", "NFR-009", "G2-streak"):
        assert rows[qm].status.startswith("OWNER-BLOCKED"), (qm, rows[qm].status)
    assert rows["QM-031"].status.startswith("OWNER-BLOCKED") and rows["QM-036(b)"].status.startswith("OWNER-BLOCKED")


def test_the_consecutive_counter_resets_on_a_failure_and_skips_input_errors() -> None:
    log = [rec(i) for i in range(5)]
    assert report.consecutive_completed(log) == 5
    log.append(rec(5, "failed", "verification_failed"))
    assert report.consecutive_completed(log) == 0
    log += [rec(6), rec(7, "excluded", "file_rejected"), rec(8)]
    assert report.consecutive_completed(log) == 2  # the input error neither counts nor resets


def test_the_success_rate_excludes_exactly_the_listed_input_errors() -> None:
    log = [rec(i) for i in range(97)]
    log += [rec(97, "excluded", "file_rejected"), rec(98, "excluded", "unsupported_media")]
    log += [rec(99, "failed", "verification_failed")]
    rate, ok, counted = report.success_rate(log)
    assert (ok, counted) == (97, 98)  # hand-worked: 100 attempts, 2 excluded, 1 pipeline failure
    assert rate == pytest.approx(97 / 98)
    # a failure that is NOT an input error counts, whatever its stage
    for code in ("insufficient_storage", "stock_unavailable", "timeout", "internal_error"):
        assert report.success_rate([rec(0), rec(1, "failed", code)])[2] == 2


def test_a_hundred_consecutive_clean_renders_pass_the_count_rows() -> None:
    rows = {r.id: r for r in report.build_rows([rec(i) for i in range(100)], FACTS)}
    assert rows["G2-streak"].status == "PASS"
    assert rows["NFR-009"].status == "PASS"
    assert rows["QM-038"].status == "PASS"
    bad = [rec(i) for i in range(100)]
    bad[40] = rec(40, checks=[{"id": "QM-038", "ok": False, "detail": "repeat"}])
    assert {r.id: r for r in report.build_rows(bad, FACTS)}["QM-038"].status == "FAIL"


def test_timing_rows_are_shown_but_not_gates_below_twenty_runs_and_blame_other_hardware() -> None:
    smoke = {r.id: r for r in report.build_rows([rec(i) for i in range(3)], FACTS)}
    assert smoke["QM-085"].status.startswith("NOT MEASURED (n = 3")
    assert "p95" in smoke["QM-085"].value and "client-observed" in smoke["QM-085"].evidence
    slow = [rec(i, timings={**rec(0)["timings"], "draft_s": 400.0}) for i in range(25)]
    assert {r.id: r for r in report.build_rows(slow, FACTS)}["QM-085"].status == "FAIL"
    odd = {"cpu_count": 12, "tuning": {"ffmpeg_threads": 6}, "anthropic_configured": False}
    assert {r.id: r for r in report.build_rows(slow, odd)}["QM-085"].status.startswith("FAIL (hardware differs:")


def test_the_pexels_skip_marks_the_rows_pending() -> None:
    rows = report.build_rows([], FACTS, stock="pexels", pexels_skipped=True)
    assert [r.status.split(" ")[0] for r in rows] == ["PENDING"]
    assert "SKIPPED (no PEXELS_API_KEY)" in rows[0].evidence


def test_the_verdict_never_calls_pending_work_a_pass() -> None:
    rows = report.build_rows([rec(i) for i in range(3)], FACTS)
    assert report.verdict(rows).startswith("G2 NOT DECIDED: owner steps pending")
    failing = report.build_rows([rec(i, checks=[{"id": "QM-038", "ok": False, "detail": "x"}]) for i in range(100)], FACTS)
    assert report.verdict(failing).startswith("Fix pipeline; no UI polish")


def test_results_files_have_the_documented_columns(tmp_path: Path) -> None:
    rows = report.build_rows([rec(0)], FACTS)
    csv_path, md_path = report.write_results(tmp_path, "run1", rows, {"cpu_count": 4})
    with csv_path.open() as fh:
        header = next(csv.reader(fh))
    assert tuple(header) == report.COLUMNS
    assert "cpu_count: 4" in md_path.read_text()


# --- the review sheets ---------------------------------------------------------------------------
def test_the_audit_sheet_has_exactly_100_blank_rows_when_100_segments_exist(tmp_path: Path) -> None:
    kept = tmp_path / "kept.mp4"
    kept.write_bytes(b"x")
    log = [rec(i, master_path=str(kept) if i % 2 == 0 else None) for i in range(25)]  # 25 renders x 4 cuts = 100
    audit_path, keywords_path = sheets.write_sheets(tmp_path, "run1", log)
    with audit_path.open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 100
    assert all(r["hard_cut_seen"] == "" for r in rows)  # never filled by the tooling
    assert {r["master_path"] for r in rows} == {str(kept), sheets.NOT_KEPT}
    with keywords_path.open() as fh:
        kw = list(csv.DictReader(fh))
    assert len(kw) == 25 and all(r["relevance_1_to_5"] == "" for r in kw)
    assert kw[0]["keywords_in_plan"] == "night; city"


def test_one_segment_per_render_when_a_hundred_renders_exist() -> None:
    picked = sheets.sample_segments([rec(i) for i in range(120)])
    assert len(picked) == 100
    assert len({r["render_id"] for r, _ in picked}) == 100


def test_fewer_segments_than_the_sample_are_all_listed() -> None:
    assert len(sheets.sample_segments([rec(0), rec(1)])) == 8


def test_a_master_that_was_not_kept_says_so_even_if_a_path_was_recorded(tmp_path: Path) -> None:
    rows = sheets.audit_rows([rec(0, master_path=str(tmp_path / "gone.mp4"))])
    assert {r[4] for r in rows} == {sheets.NOT_KEPT}


def test_the_sheets_module_has_no_code_that_fills_an_answer_column() -> None:
    src = Path(sheets.__file__).read_text()
    assert src.count('""') >= 2  # the answer cells are literal empty strings
    assert "hard_cut_seen" in src and "yes" not in src.lower().replace("yes` in", "")

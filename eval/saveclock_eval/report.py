"""The results table (CSV and Markdown) and the numbers behind it (plan 009, Step 7).

Every row carries exactly one status word: PASS, FAIL, NOT MEASURED, PENDING or OWNER-BLOCKED,
optionally followed by a parenthesis. A row that was not measured never renders as PASS: a
count-gated row stays OWNER-BLOCKED until a run really holds the 100 consecutive renders.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from saveclock_eval.stats import percentiles

STATUS_WORDS = ("PASS", "FAIL", "NOT MEASURED", "PENDING", "OWNER-BLOCKED")
COLUMNS = ("id", "description", "value", "target", "hard_limit", "status", "n", "evidence")
SOAK_RENDERS = 100  # G2: 100 consecutive renders
MIN_TIMING_N = 20  # G0-13: at least 20 runs before a percentile is a gate
THRESHOLDS = Path(__file__).resolve().parent.parent / "thresholds.json"
EXCLUDED = Path(__file__).resolve().parent.parent / "excluded_errors.json"
NO_GOLDEN = "NOT MEASURED (no golden set, DECISIONS §8g, RQ-5)"
SYNTH_DOWNBEAT_LABEL = "report only (clicks carry no bar accent)"
NOT_GATED_SYNTH_DOWNBEAT = "not gated: " + SYNTH_DOWNBEAT_LABEL
REF_CPUS, REF_THREADS = 4, 4  # QUALITY states its speed gates for 4 vCPU with 4 threads


@dataclass(frozen=True)
class Row:
    id: str
    description: str
    value: str
    target: str
    hard_limit: str
    status: str
    n: str
    evidence: str

    def cells(self) -> list[str]:
        return [getattr(self, c) for c in COLUMNS]


def status_word(status: str) -> str | None:
    """The leading status word, or None when the text is not in the vocabulary."""
    return next((w for w in STATUS_WORDS if status == w or status.startswith(w + " (")), None)


def thresholds() -> dict[str, dict[str, Any]]:
    return {k: v for k, v in json.loads(THRESHOLDS.read_text()).items() if not k.startswith("_")}


def excluded_codes() -> frozenset[str]:
    return frozenset(json.loads(EXCLUDED.read_text())["error_codes"])


# --- the soak counters -----------------------------------------------------------------------
def consecutive_completed(records: list[dict[str, Any]]) -> int:
    """The current run of completed renders at the end of the log. A failure resets it to 0; an
    excluded input error neither counts nor resets (it is not the pipeline's fault)."""
    streak = 0
    for rec in records:
        if rec["outcome"] == "completed":
            streak += 1
        elif rec["outcome"] == "failed":
            streak = 0
    return streak


def success_rate(records: list[dict[str, Any]], excluded: frozenset[str] | None = None) -> tuple[float, int, int]:
    """NFR-009: completed / (completed + failed); input errors in `excluded` are left out of both."""
    excluded = excluded_codes() if excluded is None else excluded
    counted = [r for r in records if not (r["outcome"] != "completed" and r.get("error_code") in excluded)]
    done = sum(1 for r in counted if r["outcome"] == "completed")
    return (done / len(counted) if counted else 0.0), done, len(counted)


# --- machine facts ---------------------------------------------------------------------------
def hardware_differs(facts: dict[str, Any]) -> str | None:
    """The text of D-4 when the machine is not the one QUALITY states its speed gates for."""
    tuning = facts.get("tuning") or {}
    threads = tuning.get("ffmpeg_threads")
    if facts.get("cpu_count") != REF_CPUS or (threads is not None and threads != REF_THREADS):
        return f"{facts.get('cpu_count')} CPUs, ffmpeg threads {threads}, QUALITY states 4 vCPU with 4 threads"
    return None


# --- rows ------------------------------------------------------------------------------------
def _gate(value: float, spec: dict[str, Any]) -> bool:
    return value >= spec["floor"] if "floor" in spec else value <= spec["max"]


def _fmt(spec: dict[str, Any]) -> str:
    return f">= {spec['floor']}" if "floor" in spec else f"<= {spec['max']}"


def _downbeat_debug(done: list[dict[str, Any]]) -> str:
    """Why the downbeat F1 is what it is, per track: estimated and reference downbeat counts and the
    best phase offset in beats (0 = the grid is right, only the bar start differs otherwise)."""
    parts = [
        f"{r['label']}: est {d['n_est']}, ref {d['n_ref']}, best phase {d['best_phase_beats']} beats"
        for r in done
        if (d := (r.get("beat") or {}).get("downbeat_debug"))
    ]
    return "per track: " + ("; ".join(parts) if parts else "no debug data in this run")


def _timing_row(
    row_id: str, description: str, values: list[float], spec: dict[str, Any], facts: dict[str, Any], observed: str
) -> Row:
    target, hard = f"<= {spec['target']} s", f"<= {spec['hard']} s"
    if not values:
        return Row(row_id, description, "no data", target, hard, "NOT MEASURED (no completed render)", "0", observed)
    p = percentiles(values)
    shown = f"p50 {p['p50']:.1f} s, p95 {p['p95']:.1f} s, max {p['max']:.1f} s"
    if len(values) < MIN_TIMING_N:
        status = f"NOT MEASURED (n = {len(values)} < {MIN_TIMING_N}: shown, not a gate)"
    elif p["p95"] <= spec["hard"]:
        status = "PASS" if p["p95"] <= spec["target"] else "PASS (hard limit met, target missed)"
    else:
        differs = hardware_differs(facts)
        status = f"FAIL (hardware differs: {differs})" if differs else "FAIL"
    return Row(row_id, description, shown, target, hard, status, str(len(values)), observed)


def _count_row(row_id: str, description: str, fails: int, n: int, streak: int, evidence: str) -> Row:
    """A count-gated row: OWNER-BLOCKED until the run holds the 100 consecutive renders."""
    value = f"{n - fails}/{n} clean"
    if streak < SOAK_RENDERS:
        status = f"OWNER-BLOCKED (soak on the owner's PC; {streak} consecutive so far, {SOAK_RENDERS} needed)"
    else:
        status = "PASS" if fails == 0 else "FAIL"
    return Row(row_id, description, value, "0 failures over 100 consecutive renders", "", status, str(n), evidence)


def _check_fails(records: list[dict[str, Any]], prefix: str) -> tuple[int, int]:
    seen = [r for r in records if r["outcome"] == "completed"]
    rel = [[c for c in r["checks"] if c["id"].startswith(prefix)] for r in seen]
    have = [cs for cs in rel if cs]
    return sum(1 for cs in have if not all(c["ok"] for c in cs)), len(have)


def _verify_fails(records: list[dict[str, Any]], qm: str) -> tuple[int, int]:
    with_verify = [r for r in records if r["outcome"] == "completed" and r.get("verify")]
    if qm == "QM-068":
        with_verify = [r for r in with_verify if r.get("mode_a")]
    bad = sum(1 for r in with_verify if any(f["id"] == qm and f["level"] == "block" for f in r["verify"]["failed"]))
    return bad, len(with_verify)


def build_rows(
    records: list[dict[str, Any]], facts: dict[str, Any], *, stock: str = "fake", pexels_skipped: bool = False
) -> list[Row]:
    th = thresholds()
    done = [r for r in records if r["outcome"] == "completed"]
    streak = consecutive_completed(records)
    rows: list[Row] = []
    machine = f"{facts.get('cpu_count')} CPUs; tuning {json.dumps(facts.get('tuning'), sort_keys=True)}"

    if pexels_skipped:
        why = "PENDING (needs PEXELS_API_KEY on the stack; no real-stock result is faked)"
        return [Row("real-stock", "real-stock rows (audit sheet source, live smoke)", "-", "-", "", why, "0", "SKIPPED (no PEXELS_API_KEY)")]

    # golden-set core numbers: not measured, never PASS
    for key, label in (("beat_f1", "Beat F1 @70 ms"), ("cmlt", "CMLt"), ("amlt", "AMLt"),
                       ("downbeat_f1", "Downbeat F1 @70 ms"), ("octave_error_rate", "Octave error rate")):
        rows.append(Row(th[key]["qm"], f"{label}, golden core set", "-", _fmt(th[key]), "", NO_GOLDEN, "0", "owner decides at G2 whether to build a small golden set (RQ-5)"))

    # the same metrics on the synthetic click tracks (known grid): measured, labelled as such
    beats = [r["beat"] for r in done if r.get("beat")]
    for key, field, label in (("beat_f1", "f_measure", "Beat F1"), ("cmlt", "cmlt", "CMLt"),
                              ("amlt", "amlt", "AMLt"), ("downbeat_f1", "downbeat_f1", "Downbeat F1")):
        vals = [b[field] for b in beats if b.get(field) is not None]
        spec = th[key]
        if vals:
            mean = float(np.mean(vals))
            status, desc, note = "PASS" if _gate(mean, spec) else "FAIL", f"{label}, synthetic click tracks (known grid; not the golden set)", "mean over renders; untrimmed, 70 ms"
            if key == "downbeat_f1":  # clicks carry no bar accent, so a low value is not a pipeline finding
                status = "PASS (report only)" if status == "PASS" else f"FAIL ({NOT_GATED_SYNTH_DOWNBEAT})"
                desc, note = f"{desc}: {SYNTH_DOWNBEAT_LABEL}", f"{note}; {_downbeat_debug(done)}"
            rows.append(Row(f"{spec['qm']}/synth", desc, f"{mean:.4f}", _fmt(spec), "", status, str(len(vals)), note))
        else:
            rows.append(Row(f"{spec['qm']}/synth", f"{label}, synthetic click tracks", "-", _fmt(spec), "", "NOT MEASURED (no annotated track in this run)", "0", ""))
    octs = [b["octave_error"] for b in beats if b.get("octave_error") is not None]
    spec = th["octave_error_rate"]
    rows.append(Row("QM-016/synth", "Octave error rate, synthetic click tracks", f"{np.mean(octs):.4f}" if octs else "-", _fmt(spec), "",
                    ("PASS" if _gate(float(np.mean(octs)), spec) else "FAIL") if octs else "NOT MEASURED (no annotated track in this run)", str(len(octs)), ""))
    tempo = [b["tempo_abs_err"] for b in beats if b.get("tempo_abs_err") is not None]
    rows.append(Row("tempo", "Tempo error vs the known BPM (mean absolute, BPM)", f"{np.mean(tempo):.3f}" if tempo else "-", "report only", "", "PASS (no target, reported)" if tempo else "NOT MEASURED (no annotated track)", str(len(tempo)), ""))
    conf = [r["confidence"] for r in done if r.get("confidence") is not None]
    rows.append(Row("confidence", "Analysis confidence score (mean)", f"{np.mean(conf):.3f}" if conf else "-", "report only", "", "PASS (no target, reported)" if conf else "NOT MEASURED (no completed render)", str(len(conf)), ""))
    sect = [r["n_sections"] for r in done if r.get("n_sections") is not None]
    rows.append(Row("sections", "Sections found (mean count; energy labels e1..e4)", f"{np.mean(sect):.1f}" if sect else "-", "report only", "", "PASS (no target, reported)" if sect else "NOT MEASURED (no completed render)", str(len(sect)), ""))

    # QM-026 musical alignment of planned cuts
    al = [r["alignment"] for r in done if r.get("alignment") is not None]
    spec = th["alignment"]
    rows.append(Row("QM-026", "Planned cuts within 70 ms of an annotated beat (synthetic grid; owner songs if given)", f"{np.mean(al):.4f}" if al else "-", _fmt(spec), "",
                    ("PASS" if _gate(float(np.mean(al)), spec) else "FAIL") if al else "NOT MEASURED (no annotated track in this run)", str(len(al)), "mean share per render"))

    # timings
    observed = "client-observed wall time between state changes (upper bound: includes queueing and the 0.5 s poll)"
    rows.append(_timing_row("QM-080", "Analysis p95 (upload accepted to analysis available)", [r["timings"]["analysis_s"] for r in done if r["timings"].get("analysis_s") is not None], th["analysis_p95_s"], facts, observed))
    rows.append(_timing_row("QM-085", "Draft p95 (upload accepted to draft ready)", [r["timings"]["draft_s"] for r in done if r["timings"].get("draft_s") is not None], th["draft_p95_s"], facts, observed))
    rows.append(_timing_row("QM-081", "Render p95 (plan to verified silent master)", [r["timings"]["render_ms"] / 1000 for r in done if r["timings"].get("render_ms") is not None], th["render_p95_s"], facts, "server-measured: verify.render_ms"))
    rows.append(_timing_row("QM-086", "Mode A remux p95 (request to ready)", [r["timings"]["mode_a_s"] for r in done if r["timings"].get("mode_a_s") is not None], th["mode_a_p95_s"], facts, observed))
    ratios = [r["timings"]["verify_ms"] / r["timings"]["render_ms"] for r in done if r["timings"].get("render_ms") and r["timings"].get("verify_ms") is not None]
    spec = th["verify_overhead_ratio"]
    status = "NOT MEASURED (no completed render)" if not ratios else ("PASS" if float(np.mean(ratios)) <= spec["max"] else "FAIL (not gated, reported only)")
    rows.append(Row("QM-082", "Verification time / render time (mean)", f"{np.mean(ratios):.2f}" if ratios else "-", _fmt(spec), "", status, str(len(ratios)), "reported, not gated (plan 009)"))
    rows.append(Row("QM-083", "Peak RSS and CPU-seconds per stage", "-", "report only", "", "NOT MEASURED (per-stage RSS needs cgroup sampling; not built)", "0", ""))

    # per-render Block checks and the independent re-probes: count-gated
    n_done = len(done)
    for qm, label in (("QM-060", "container/stream probe"), ("QM-061", "CFR 30 fps"), ("QM-062", "frame count"),
                      ("QM-063", "duration"), ("QM-064", "cut position vs plan"), ("QM-068", "A/V drift")):
        fails, n = _verify_fails(records, qm)
        rows.append(_count_row(qm, f"{label} (the render's own verify, Block)", fails, n, streak, f"smoke/soak counts from verify.failed; {machine}"))
    for prefix, rid, label in (("QM-060..063", "QM-060..063/host", "host ffprobe re-probe of the downloaded files"),
                               ("QM-064/oracle", "QM-064/oracle", "cut frames vs the exact-arithmetic frame rule"),
                               ("QM-038", "QM-038", "no repeated clip"),
                               ("QM-036(a)", "QM-036(a)", "detector: no cut off a planned cut (PySceneDetect on the master)"),
                               ("QM-087", "QM-087", "Mode A integrity (video packets equal the master)")):
        fails, n = _check_fails(records, prefix)
        rows.append(_count_row(rid, label, fails, n, streak, "eval re-probe, independent of the service"))
    rows.append(Row("QM-069", "Sync canary", "-", "|offset| <= 1 frame", "", "PENDING (make golden: the coordinator pastes its last line)", "0", "see make golden"))

    # success rate and the streak
    rate, ok, counted = success_rate(records)
    excl: dict[str, int] = {}
    for r in records:
        if r["outcome"] == "excluded":
            excl[r.get("error_code") or "?"] = excl.get(r.get("error_code") or "?", 0) + 1
    spec = th["success_rate"]
    status = f"OWNER-BLOCKED (soak on the owner's PC; {streak} consecutive so far, {SOAK_RENDERS} needed)" if streak < SOAK_RENDERS else ("PASS" if rate >= spec["floor"] else "FAIL")
    rows.append(Row("NFR-009", "Render success rate (excluding input errors)", f"{ok}/{counted} = {rate:.4f}", _fmt(spec), "", status, str(counted), f"excluded input errors: {json.dumps(excl, sort_keys=True)}"))
    rows.append(Row("G2-streak", "Consecutive completed renders", str(streak), f">= {SOAK_RENDERS}", "", "OWNER-BLOCKED (soak on the owner's PC)" if streak < SOAK_RENDERS else "PASS", str(n_done), "a failure resets this counter; the partial file keeps the history"))

    # offline keywords (FR-050)
    sources = sorted({r["keyword_source"] for r in done if r.get("keyword_source")})
    keyed = bool(facts.get("anthropic_configured"))
    if not sources:
        fr = "NOT MEASURED (no completed render)"
    elif sources == ["table"] and not keyed:
        fr = "PASS"
    elif keyed:
        fr = "PENDING (an Anthropic key is configured on this stack: run it without one)"
    else:
        fr = f"PENDING (keyword sources {sources} with no key: the stack serves fake keywords, so the offline table was not exercised)"
    rows.append(Row("FR-050", "Offline keyword run: a draft with no Anthropic key", ", ".join(sources) or "-", "keyword_source == table, no key", "", fr, str(len(done)), f"stock: {stock}; anthropic key configured: {keyed}"))

    # the human rows
    rows.append(Row("QM-031", "Keyword relevance (owner score 1-5)", "-", f">= {th['keyword_relevance_mean']['floor']} mean", "", "OWNER-BLOCKED (review sheet: <run-id>-keywords.csv)", "0", "the sheet is generated blank and never filled by the tooling"))
    rows.append(Row("QM-036(b)", "Share of used segments with a human-confirmed hard cut (100-segment audit)", "-", f"<= {th['internal_cut_audit_share']['max']:.0%}", "", "OWNER-BLOCKED (review sheet: <run-id>-audit.csv)", "0", "the sheet is generated blank and never filled by the tooling"))
    return rows


# --- writing ---------------------------------------------------------------------------------
def write_results(out_dir: Path, run_id: str, rows: list[Row], facts: dict[str, Any]) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path, md_path = out_dir / f"{run_id}.csv", out_dir / f"{run_id}.md"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(COLUMNS)
        w.writerows(r.cells() for r in rows)
    lines = [f"# Eval results {run_id}", "", "## Machine and run facts", ""]
    lines += [f"- {k}: {json.dumps(v, sort_keys=True) if isinstance(v, dict) else v}" for k, v in facts.items()]
    lines += ["", "## Results", "", "| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    lines += ["| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in r.cells()) + " |" for r in rows]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, md_path


def verdict(rows: list[Row]) -> str:
    """G2's reading of the table: a gated FAIL means 'Fix pipeline; no UI polish'; owner rows pending."""
    failed = [r.id for r in rows if status_word(r.status) == "FAIL" and "(not gated" not in r.status]
    if failed:
        return f"Fix pipeline; no UI polish (failing rows: {', '.join(failed)})"
    pending = [r.id for r in rows if status_word(r.status) == "OWNER-BLOCKED"]
    return f"G2 NOT DECIDED: owner steps pending ({len(pending)} rows OWNER-BLOCKED)" if pending else "all measured rows pass: the owner decides G2"

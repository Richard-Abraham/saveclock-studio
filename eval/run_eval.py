#!/usr/bin/env python3
"""The one eval script (DECISIONS 8d, plan 009): G2 evidence against a RUNNING stack.

It never starts a stack and never touches a database: it talks to the API (loopback only), makes
projects from generated click tracks (and the owner's songs when `eval/manifests/local.json`
exists), drives each through upload, draft, render and Mode A, measures what the plan asks for,
deletes what it created, and writes `eval/results/<run-id>.csv`, `.md` and the two blank review
sheets. It never fills a sheet and never decides G2.

  make eval-smoke     3 renders, one per tempo (minutes)
  make eval-soak      100 consecutive renders, masters kept for the human audit (hours; the owner's PC)

Run it from services/api:  uv --directory services/api run --group eval python ../../eval/run_eval.py --help
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from saveclock_eval import checks, report, sheets
from saveclock_eval.annot import read_beats
from saveclock_eval.client import (
    WAIT_DRAFT_S,
    WAIT_MODE_A_S,
    WAIT_RENDER_S,
    ApiFailure,
    EvalClient,
    Refused,
    WaitTimeout,
    wait_until,
)
from saveclock_eval.metrics import alignment_share, downbeat_debug, evaluate_track

EVAL_DIR = Path(__file__).resolve().parent
REPO = EVAL_DIR.parent
FPS = 30
MASTER_MB = 40  # a stated estimate (a 30 s 1080x1920 master), replaced by the measured mean after a smoke run
MAX_EXTRA_ATTEMPTS = 20  # a soak that keeps failing stops after this many attempts beyond N
HARD_IDS = ("QM-060..063", "QM-064/oracle", "QM-038", "QM-087")  # check ids whose failure is a finding
TERMINAL_UI = {"failed", "canceled"}


# --- manifests -------------------------------------------------------------------------------
def load_entries(manifest: Path, local: Path | None) -> list[dict[str, Any]]:
    """Generated click tracks from the manifest, then the owner's songs from `local` (if any)."""
    entries = [{**t, "kind": "synth"} for t in json.loads(manifest.read_text()).get("tracks", [])]
    if local is not None and local.is_file():
        entries += [{**s, "kind": "owner"} for s in json.loads(local.read_text()).get("songs", [])]
    return entries


def smoke_entries(entries: list[dict[str, Any]], n: int = 3) -> list[dict[str, Any]]:
    """One generated track per distinct tempo (the shortest first), `n` of them."""
    picked: dict[float, dict[str, Any]] = {}
    for e in sorted((e for e in entries if e["kind"] == "synth"), key=lambda e: (e["duration_s"], e["label"])):
        picked.setdefault(e["bpm"], e)
    return sorted(picked.values(), key=lambda e: e["bpm"])[:n]


def make_track(entry: dict[str, Any], cache: Path) -> tuple[Path, np.ndarray | None, np.ndarray | None]:
    """The song file and its ground-truth beats and downbeats (None when unannotated)."""
    if entry["kind"] == "owner":
        beats = entry.get("beats")
        if beats and Path(beats).is_file():
            times, mask = read_beats(Path(beats))
            return Path(entry["path"]), times, times[mask]
        return Path(entry["path"]), None, None
    wav = cache / f"{entry['bpm']}-{entry['duration_s']}-{entry['lead_s']}.wav"
    out = subprocess.run(  # noqa: S603 - the repo's own generator, fixed arguments
        [sys.executable, str(EVAL_DIR / "scripts" / "make_click_track.py"), "--bpm", str(entry["bpm"]),
         "--duration", str(entry["duration_s"]), "--lead", str(entry["lead_s"]), "--out", str(wav)],
        capture_output=True, text=True, check=True, timeout=120,
    )
    grid = json.loads(out.stdout)
    return wav, np.asarray(grid["beats_s"]), np.asarray(grid["downbeats_s"])


# --- machine facts -----------------------------------------------------------------------------
def machine_facts(client_settings: dict[str, Any], ffmpeg: str, args: argparse.Namespace, run_id: str) -> dict[str, Any]:
    ram_gb = None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                ram_gb = round(int(line.split()[1]) / 1048576, 1)
    except OSError:
        pass
    try:
        build = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True, check=True, timeout=30).stdout.splitlines()[0]  # noqa: S603
    except (OSError, subprocess.SubprocessError):
        build = "unknown"
    keys = client_settings.get("keys", {})
    return {
        "run_id": run_id,
        "mode": "smoke" if args.smoke else f"soak {args.soak}",
        "stock": args.stock,
        "api_url": args.api_url,
        "cpu_count": os.cpu_count(),
        "ram_gb": ram_gb,
        "host_ffmpeg": build,
        "tuning": client_settings.get("tuning"),
        "disk": {k: v for k, v in client_settings.get("disk", {}).items() if k in {"volume", "low"}},
        "anthropic_configured": bool(keys.get("anthropic", {}).get("configured")),
        "pexels_configured": bool(keys.get("pexels", {}).get("configured")),
    }


# --- one attempt -------------------------------------------------------------------------------
def run_one(client: EvalClient, entry: dict[str, Any], index: int, args: argparse.Namespace, work: Path, run_id: str) -> dict[str, Any]:  # noqa: PLR0912, PLR0915
    ffprobe = str(args.ffprobe)
    ffmpeg = str(Path(args.ffprobe).with_name("ffmpeg"))
    excluded = report.excluded_codes()
    rec: dict[str, Any] = {
        "index": index, "label": entry["label"], "song_label": entry["label"], "bpm": entry.get("bpm"),
        "outcome": "completed", "error_code": None, "stage": None, "project_id": None, "render_id": None,
        "timings": {}, "verify": None, "checks": [], "beat": None, "alignment": None, "keywords": [],
        "keyword_source": None, "cuts": [], "tempo_bpm": 0.0, "master_path": None, "hard_failures": [],
        "started": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    pid: str | None = None
    stage = "create"
    try:
        song, ref, ref_down = make_track(entry, work / "tracks")
        wall = time.monotonic()
        duration = 60 if entry.get("duration_s", 30) >= 60 else 30  # noqa: PLR2004
        options = {"duration": duration, "style": "default", "density": 0}
        if entry.get("vibe"):
            options["vibe"] = entry["vibe"]
        pid = client.create_project(entry.get("title") or entry["label"], options)
        rec["project_id"] = pid
        stage = "upload"
        client.upload(pid, song)
        stage = "analysis"
        _, analysis_s = wait_until(lambda: client.project(pid), lambda p: p["analysis"] is not None or p["ui_status"] in TERMINAL_UI, timeout_s=WAIT_DRAFT_S)
        stage = "draft"
        project, more = wait_until(lambda: client.project(pid), lambda p: p["ui_status"] in {"draft", *TERMINAL_UI}, timeout_s=WAIT_DRAFT_S)
        if project["ui_status"] != "draft":
            rec.update(outcome="failed", stage=stage, error_code=project.get("status_reason") or project["ui_status"])
            return rec
        rec["timings"].update(analysis_s=analysis_s, draft_s=analysis_s + more)
        analysis, plan = client.analysis(pid), client.plan(pid)
        rec["tempo_bpm"] = analysis["tempo_bpm"]
        rec["confidence"] = analysis["confidence"]["score"]
        rec["n_sections"] = len(analysis["sections"])
        rec["keyword_source"] = plan["provenance"]["keyword_source"]
        rec["keywords"] = sorted({k for c in plan["cuts"] for k in c["clip"]["keywords"]})
        t0 = plan["segment"]["start_s"]
        rec["cuts"] = [
            {"index": c["index"], "start_s": c["out_start_frame"] / FPS, "end_s": c["out_end_frame"] / FPS} for c in plan["cuts"]
        ]
        if ref is not None:
            est, est_down = np.asarray(analysis["beats_s"]), np.asarray(analysis["downbeats_s"])
            ref_d = ref_down if ref_down is not None and len(ref_down) else None
            m = evaluate_track(ref, est, ref_d, est_down)  # no estimated downbeat: an empty array scores 0, not "unmeasured"
            rec["beat"] = {k: m[k] for k in ("f_measure", "cmlt", "amlt", "downbeat_f1", "octave_error")}
            if ref_d is not None:
                rec["beat"]["downbeat_debug"] = downbeat_debug(ref, ref_d, est_down)
            if entry.get("bpm"):
                rec["beat"]["tempo_abs_err"] = abs(analysis["tempo_bpm"] - entry["bpm"])
            rec["alignment"] = alignment_share([c["out_start_frame"] / FPS + t0 for c in plan["cuts"]], ref)
        cks = [checks.check_cut_frames(plan), checks.check_no_repeats(plan, project["flags"])]
        stage = "render"
        rid = client.create_render(pid)
        rec["render_id"] = rid
        render, _ = wait_until(lambda: client.render(rid), lambda r: r["state"] in {"ready", "failed", "canceled"}, timeout_s=WAIT_RENDER_S)
        if render["state"] != "ready":
            rec.update(outcome="failed", stage=stage, error_code=render.get("error_code") or render["state"])
            return rec
        v = render["verify"]
        if v:
            rec["verify"] = {k: v[k] for k in ("passed", "blocks", "warns", "failed")}
            rec["timings"].update(render_ms=v["render_ms"], verify_ms=v["verify_ms"])
            if not v["passed"]:
                cks.append(checks.Check("verify", False, f"the render's own verify blocked: {[f['id'] for f in v['failed']]}"))
        stage = "download"
        master = work / f"{rid}-master.mp4"
        client.download(rid, "silent_video", master)
        cks += checks.check_probe(checks.ffprobe_json(ffprobe, master), master, plan["total_frames"], with_audio=False)
        cks.append(checks.check_detected_cuts(checks.detect_cuts(master), plan))
        stage = "mode_a"
        client.request_mode_a(rid)
        ma, mode_a_s = wait_until(lambda: client.render(rid), lambda r: r["mode_a_state"] in {"ready", "failed"}, timeout_s=WAIT_MODE_A_S)
        if ma["mode_a_state"] != "ready":
            rec.update(outcome="failed", stage=stage, error_code="mode_a_failed")
            return rec
        rec["mode_a"] = True
        rec["timings"]["mode_a_s"] = mode_a_s
        if ma.get("verify"):  # the remux re-verifies: QM-067/068 and the audio checks land here
            rec["verify"] = {k: ma["verify"][k] for k in ("passed", "blocks", "warns", "failed")}
        with_song = work / f"{rid}-with_song.mp4"
        client.download(rid, "with_song", with_song)
        cks += checks.check_probe(checks.ffprobe_json(ffprobe, with_song), with_song, plan["total_frames"], with_audio=True)
        cks.append(checks.check_mode_a_integrity(ffmpeg, master, with_song))
        rec["checks"] = [c.as_dict() for c in cks]
        rec["hard_failures"] = [c.id for c in cks if not c.ok and c.id.startswith(HARD_IDS + ("verify",))]
        if args.keep_masters:
            dest = Path(args.keep_masters) / run_id
            dest.mkdir(parents=True, exist_ok=True)
            rec["master_path"] = str(shutil.copy2(master, dest / f"{rid}.mp4"))
        if rec["hard_failures"]:  # a finding: keep what it needs for the report
            keep = REPO / ".data" / "eval-failures" / rid
            keep.mkdir(parents=True, exist_ok=True)
            for f in (master, with_song):
                shutil.copy2(f, keep / f.name)
            (keep / "plan.json").write_text(json.dumps(plan, indent=1))
            rec["plan_content_hash"] = plan["content_hash"]
            rec["artefacts"] = str(keep)
        for f in (master, with_song):
            f.unlink(missing_ok=True)
        rec["wall_s"] = time.monotonic() - wall
    except ApiFailure as exc:
        rec.update(outcome="excluded" if exc.code in excluded else "failed", stage=stage, error_code=exc.code)
    except WaitTimeout:
        rec.update(outcome="failed", stage=stage, error_code="timeout")
    finally:
        if pid and not args.keep and not rec["hard_failures"]:  # a hard failure stays as evidence; failed and excluded runs are cleaned too
            try:
                client.delete_project(pid)
            except ApiFailure:
                rec["cleanup"] = "delete failed"
    return rec


# --- the run -------------------------------------------------------------------------------------
def parse(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--api-url", default="http://127.0.0.1:8000", help="the running API (loopback only)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--smoke", action="store_true", help="3 renders, one per tempo")
    mode.add_argument("--soak", type=int, metavar="N", help="N consecutive completed renders")
    p.add_argument("--resume", metavar="RUN_ID", help="continue a run from its .partial.json")
    p.add_argument("--stock", choices=["fake", "pexels"], default="fake", help="what the stack's workers serve")
    p.add_argument("--manifest", type=Path, default=EVAL_DIR / "manifests" / "g2-soak.json")
    p.add_argument("--ffprobe", type=Path, default=REPO / ".data" / "ffmpeg" / "ffprobe")
    p.add_argument("--out", type=Path, default=EVAL_DIR / "results")
    p.add_argument("--keep", action="store_true", help="do not delete the projects this run made")
    p.add_argument("--keep-masters", metavar="DIR", help="keep the silent masters of the run here (git-ignored)")
    p.add_argument("--live", action="store_true", help="allow the owner's own songs (eval/manifests/local.json)")
    args = p.parse_args(argv)
    if not (args.smoke or args.soak or args.resume):
        p.error("choose --smoke, --soak N or --resume RUN_ID")
    return args


def save_partial(path: Path, run_id: str, facts: dict[str, Any], records: list[dict[str, Any]], n_target: int, mode: str) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"run_id": run_id, "facts": facts, "records": records, "n_target": n_target, "mode": mode}, indent=1))
    tmp.replace(path)


def load_partial(path: Path) -> tuple[list[dict[str, Any]], int | None, str | None]:
    """The saved records and the run's own target and mode (None for a file written before they were stored)."""
    saved = json.loads(path.read_text())
    return saved["records"], saved.get("n_target"), saved.get("mode")


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0911, PLR0912, PLR0915
    args = parse(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        client = EvalClient(args.api_url)
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    try:
        settings = client.settings()
    except (ApiFailure, Exception) as exc:  # noqa: BLE001 - any failure to reach the stack is the same message
        print(f"cannot reach the API at {args.api_url}: {type(exc).__name__}", file=sys.stderr)
        return 3
    local = EVAL_DIR / "manifests" / "local.json"
    if args.stock == "pexels" and not settings["keys"]["pexels"]["configured"]:
        run_id = args.resume or f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-pexels"
        facts = machine_facts(settings, str(Path(args.ffprobe).with_name("ffmpeg")), args, run_id)
        rows = report.build_rows([], facts, stock="pexels", pexels_skipped=True)
        report.write_results(out, run_id, rows, facts)
        print("SKIPPED (no PEXELS_API_KEY)")
        return 0
    if local.is_file() and not args.live:
        print(f"{local.name} exists: pass --live to use the owner's own songs (it is ignored otherwise)")
    entries = load_entries(args.manifest, local if args.live else None)
    run_id = args.resume or f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{'smoke' if args.smoke else 'soak'}"
    partial = out / f"{run_id}.partial.json"
    records: list[dict[str, Any]] = []
    n_target = 3 if args.smoke else (args.soak or len(entries))
    if args.resume:  # the run's own target and mode win over this command line (which names neither)
        records, saved_target, saved_mode = load_partial(partial)
        if saved_mode:
            args.smoke, args.soak = saved_mode == "smoke", (None if saved_mode == "smoke" else saved_target)
        n_target = saved_target if saved_target is not None else n_target
    mode = "smoke" if args.smoke else "soak"
    if settings["disk"]["low"]:
        print("refusing to start: the stack reports low disk space (disk.low)", file=sys.stderr)
        return 3
    need = n_target * MASTER_MB * 1_000_000 if args.keep_masters else 0
    free = settings["disk"]["volume"]["free"]
    if need and free < need:
        print(f"refusing to start: {n_target} masters need about {need / 1e9:.1f} GB (stated estimate), {free / 1e9:.1f} GB free", file=sys.stderr)
        return 3
    facts = machine_facts(settings, str(Path(args.ffprobe).with_name("ffmpeg")), args, run_id)
    work = Path(tempfile.mkdtemp(prefix="saveclock-eval-"))
    (work / "tracks").mkdir()
    plan_entries = smoke_entries(entries) if args.smoke else entries
    if not plan_entries:
        print("the manifest has no usable entry", file=sys.stderr)
        return 2
    limit = len(plan_entries) if args.smoke else n_target + MAX_EXTRA_ATTEMPTS
    try:
        while len(records) < limit:
            if not args.smoke and report.consecutive_completed(records) >= n_target:
                break
            entry = plan_entries[len(records) % len(plan_entries)]
            rec = run_one(client, entry, len(records), args, work, run_id)
            records.append(rec)
            save_partial(partial, run_id, facts, records, n_target, mode)
            print(f"[{len(records)}] {entry['label']}: {rec['outcome']}"
                  + (f" ({rec['stage']}: {rec['error_code']})" if rec["outcome"] != "completed" else "")
                  + (f" HARD FAILURE {rec['hard_failures']}" if rec["hard_failures"] else "")
                  + f" | consecutive completed: {report.consecutive_completed(records)}")
            walls = [r["wall_s"] for r in records if r.get("wall_s")]
            if walls and not args.smoke:
                print(f"    estimated time left: {np.mean(walls):.0f} s x {n_target - report.consecutive_completed(records)} (measured mean)")
    finally:
        shutil.rmtree(work, ignore_errors=True)
        client.close()
    rows = report.build_rows(records, facts, stock=args.stock)
    csv_path, md_path = report.write_results(out, run_id, rows, facts)
    sheet_paths = sheets.write_sheets(out, run_id, records)
    walls = [r["wall_s"] for r in records if r.get("wall_s")]
    if walls:
        print(f"measured mean per render {np.mean(walls):.0f} s; a {report.SOAK_RENDERS}-render soak is about {np.mean(walls) * report.SOAK_RENDERS / 3600:.1f} h (smoke mean x {report.SOAK_RENDERS})")
    print(f"results: {csv_path}")
    print(f"         {md_path}")
    print(f"sheets:  {sheet_paths[0]} / {sheet_paths[1]} (blank: for the owner)")
    print(f"verdict: {report.verdict(rows)}")
    hard = [r for r in records if r["hard_failures"] or (args.smoke and r["outcome"] == "failed")]
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())

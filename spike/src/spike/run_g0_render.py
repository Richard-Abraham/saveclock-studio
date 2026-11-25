"""G0 synthetic frame-accuracy harness (T-0.3 synthetic part; G0-10, G0-12, indicative G0-15/16).

``python -I -m spike.run_g0_render --ffmpeg <path> --out <json>``. Build-agnostic: Step 6 runs it
unchanged with the 9.0.x binary and diffs the JSON (same schema) with ``compare_builds``.
Exit code 0 only if every render, remux and mezzanine check passes.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from spike import bench, remux, verify
from spike.ffwrap import FfError, Tools, run, version_line
from spike.mezz import build_mezz
from spike.plan import Plan, build_plan
from spike.render import build_render, render_cmd
from spike.synth_clips import clip_specs, make_audio_sources, make_clips
from spike.vcodec import pick_vcodec

SCHEMA = "g0-render/1"
HOME = Path.home() / "saveclock-spike"
BPM_TAGS = ["120", "128", "133p3"]
AUDIO_EXTS = ["m4a", "mp3", "wav", "flac", "ogg"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def cases(n: int) -> list[dict[str, Any]]:
    combos = list(itertools.product(BPM_TAGS, (30, 60), (0, 1)))
    out: list[dict[str, Any]] = []
    for k in range(n):
        tag, sec, lead = combos[k % len(combos)]
        out.append(
            {
                "id": f"R{k:02d}_{tag}_{sec}s_L{lead}",
                "tag": tag,
                "seconds": sec,
                "lead": lead,
                "seed": 1000 + k,
                "downbeat_index": 0 if sec == 60 else 1 + k % 3,
                "audio_ext": AUDIO_EXTS[k % len(AUDIO_EXTS)],
            }
        )
    return out


def mezz_stage(
    tools: Tools, codec: str, clips: dict[str, Path], work: Path
) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    """Normalise all 14 clips; verify each (CFR, PTS deltas, format)."""
    mdir = work / "mezz"
    mdir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    paths: dict[str, Path] = {}
    for spec in clip_specs():
        out = mdir / f"{spec.name}.mp4"
        res = build_mezz(tools, codec, clips[spec.name], out)
        probe = verify.probe_video(tools, out)
        nb = int(next(s for s in probe["streams"] if s["codec_type"] == "video")["nb_read_frames"])
        checks = verify.video_checks(probe, 120)
        rows.append(
            {
                "name": spec.name,
                "fps": spec.fps,
                "size": spec.size,
                "sar": spec.sar,
                "gop": spec.gop,
                "nb_frames": nb,
                "pass": all(c.ok for c in checks),
                "failed": [f"{c.name}: {c.detail}" for c in checks if not c.ok],
                "frame_pts_hash": probe["frame_pts_hash"],
                "wall_s": res.wall_s,
                "rss_mb": (res.rss_kb or 0) / 1024.0,
            }
        )
        paths[spec.name] = out
    return rows, paths


def run_cases(
    tools: Tools,
    codec: str,
    work: Path,
    synth: Path,
    audio: dict[str, dict[str, Path]],
    mezz_paths: list[Path],
    mezz_frames: list[int],
    palette: verify.Rgb,
    sel: list[dict[str, Any]],
    do_remux: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rdir = work / "renders"
    rdir.mkdir(parents=True, exist_ok=True)
    renders: list[dict[str, Any]] = []
    remuxes: list[dict[str, Any]] = []
    for c in sel:
        beats = synth / f"click_{c['tag']}_60s.beats"
        plan = build_plan(
            c["id"], beats, c["seconds"], c["downbeat_index"], c["lead"], c["seed"], mezz_frames
        )
        out = rdir / f"{c['id']}.mp4"

        def go(plan: Plan = plan, out: Path = out) -> Any:
            return build_render(tools, codec, plan, mezz_paths, out)

        res, steal, attempts = bench.run_quiet(go)
        t = time.monotonic()
        v = verify.verify_render(tools, plan, out, palette)
        verify_s = time.monotonic() - t
        rec = {
            "id": c["id"],
            "params": {k: c[k] for k in ("tag", "seconds", "lead", "seed", "downbeat_index")},
            "plan": plan.to_json(),
            "n_shots": len(plan.shots),
            "stride": plan.stride,
            "render_s": res.wall_s,
            "verify_s": verify_s,
            "rss_mb": (res.rss_kb or 0) / 1024.0,
            "steal_pct": steal,
            "attempts": attempts,
            "bytes": out.stat().st_size,
            "verify": v,
        }
        renders.append(rec)
        print(
            f"  {c['id']}: {'PASS' if v['pass'] else 'FAIL'} shots={len(plan.shots)} "
            f"render={res.wall_s:.1f}s dev1f={len(v['cuts']['deviations_1f'])}",
            flush=True,
        )
        if not do_remux:
            continue
        src = audio[c["tag"]][c["audio_ext"]]
        probe = verify.probe_video(tools, out)
        aac_copy = remux.is_aac_lc(tools, src)
        rout = work / "remux" / f"{c['id']}.{c['audio_ext']}.mp4"
        rout.parent.mkdir(parents=True, exist_ok=True)

        def go_r(
            out: Path = out,
            src: Path = src,
            rout: Path = rout,
            plan: Plan = plan,
            aac: bool = aac_copy,
        ) -> Any:
            return remux.build_remux(tools, out, src, plan.t0, plan.total_frames, rout, aac)

        rres, rsteal, rattempts = bench.run_quiet(go_r)
        t = time.monotonic()
        rv = remux.verify_remux(
            tools,
            probe["packet_hashes"],
            probe["pts"],
            rout,
            src,
            plan.t0,
            plan.total_frames,
            aac_copy,
        )
        rv_s = time.monotonic() - t
        remuxes.append(
            {
                "id": c["id"],
                "source": src.name,
                "audio_ext": c["audio_ext"],
                "audio_start_s": plan.t0,
                "remux_s": rres.wall_s,
                "verify_s": rv_s,
                "rss_mb": (rres.rss_kb or 0) / 1024.0,
                "steal_pct": rsteal,
                "attempts": rattempts,
                "verify": rv,
            }
        )
        print(
            f"  remux {c['id']} ({c['audio_ext']}, {'copy' if aac_copy else 'aac'}): "
            f"{'PASS' if rv['pass'] else 'FAIL'} off0={rv['offset_start_ms']:.1f}ms "
            f"off1={rv['offset_end_ms']:.1f}ms {rres.wall_s:.2f}s",
            flush=True,
        )
    return renders, remuxes


def parse_progress(text: str) -> dict[str, Any]:
    blocks = [ln for ln in text.splitlines() if ln.startswith("progress=")]
    last_frame = [ln for ln in text.splitlines() if ln.startswith("frame=")]
    out_time = [ln for ln in text.splitlines() if ln.startswith("out_time_us=")]
    return {
        "blocks": len(blocks),
        "ended": bool(blocks) and blocks[-1] == "progress=end",
        "last_frame": last_frame[-1] if last_frame else None,
        "last_out_time_us": out_time[-1] if out_time else None,
    }


def progress_test(
    tools: Tools, codec: str, work: Path, plan: Plan, mezz_paths: list[Path], palette: verify.Rgb
) -> dict[str, Any]:
    """T-0.3: does -progress work under -protocol_whitelist file as pipe:1 and as a file?"""
    pdir = work / "progress"
    pdir.mkdir(parents=True, exist_ok=True)
    res: dict[str, Any] = {"whitelist": "file"}
    for form in ("pipe:1", "file"):
        out = pdir / f"{form.replace(':', '')}.mp4"
        pfile = pdir / "progress.txt"
        pfile.unlink(missing_ok=True)
        arg = "pipe:1" if form == "pipe:1" else str(pfile)
        cmd = render_cmd(tools, codec, plan, mezz_paths, out, progress=arg)
        try:
            r = run(cmd, 600, check=False)
            text = (
                r.stdout.decode("utf-8", "replace")
                if form == "pipe:1"
                else (pfile.read_text() if pfile.exists() else "")
            )
            v = verify.verify_render(tools, plan, out, palette) if out.exists() else None
            res[form] = {
                "returncode": r.returncode,
                "works": r.returncode == 0 and parse_progress(text)["blocks"] > 0,
                "progress": parse_progress(text),
                "stderr_tail": r.stderr[-300:],
                "render_verified": None if v is None else v["pass"],
                "frame_pts_hash": None if v is None else v["frame_pts_hash"],
            }
        except FfError as exc:
            res[form] = {"works": False, "error": str(exc)[:300]}
    res["recommended_form"] = "file" if res.get("file", {}).get("works") else "pipe:1"
    return res


def host_info() -> dict[str, Any]:
    with open("/proc/cpuinfo", encoding="ascii") as fh:
        cpu = next((ln.split(":", 1)[1].strip() for ln in fh if ln.startswith("model name")), "?")
    import os

    return {"cpu": cpu, "logical_cpus": os.cpu_count(), "loadavg": os.getloadavg()}


def timing_table(
    renders: list[dict[str, Any]], remuxes: list[dict[str, Any]], b: dict[str, Any]
) -> str:
    def row(name: str, s: dict[str, Any], rss: float, steal: float) -> str:
        if not s.get("n"):
            return f"{name:<34}{'-':>4}"
        return (
            f"{name:<34}{s['n']:>4}{s['mean_s']:>9.2f}{s['median_s']:>9.2f}{s['p95_s']:>9.2f}"
            f"{s['max_s']:>9.2f}{rss:>9.0f}{steal:>8.2f}"
        )

    lines = [
        f"{'stage':<34}{'n':>4}{'mean_s':>9}{'med_s':>9}{'p95_s':>9}{'max_s':>9}{'rssMB':>9}{'steal%':>8}"
    ]
    main30 = [r for r in renders if r["params"]["seconds"] == 30]
    main60 = [r for r in renders if r["params"]["seconds"] == 60]
    for name, rs in (("render 30 s (main run)", main30), ("render 60 s (main run)", main60)):
        s = bench.summarize([r["render_s"] for r in rs])
        rss = max((r["rss_mb"] for r in rs), default=0.0)
        steal = max((r["steal_pct"] for r in rs), default=0.0)
        lines.append(row(name, s, rss, steal))
    s = bench.summarize([r["remux_s"] for r in remuxes])
    lines.append(
        row(
            "remux (main run)",
            s,
            max((r["rss_mb"] for r in remuxes), default=0.0),
            max((r["steal_pct"] for r in remuxes), default=0.0),
        )
    )
    if b:
        lines.append(
            row(
                "BENCH render 30 s 1080p",
                b["render"]["render_s"],
                b["render"]["rss_mb"],
                b["render"]["steal_pct"],
            )
        )
        lines.append(
            row(
                "BENCH render+verify 30 s",
                b["render"]["verified_s"],
                b["render"]["rss_mb"],
                b["render"]["steal_pct"],
            )
        )
        lines.append(
            row("BENCH remux", b["remux"]["remux_s"], b["remux"]["rss_mb"], b["remux"]["steal_pct"])
        )
        lines.append(
            row(
                "BENCH remux+verify",
                b["remux"]["verified_s"],
                b["remux"]["rss_mb"],
                b["remux"]["steal_pct"],
            )
        )
    return "\n".join(lines)


def bench_stage(
    tools: Tools,
    codec: str,
    work: Path,
    synth: Path,
    audio: dict[str, dict[str, Path]],
    mezz_paths: list[Path],
    mezz_frames: list[int],
    palette: verify.Rgb,
    n_render: int,
    n_remux: int,
) -> dict[str, Any]:
    plan = build_plan("BENCH", synth / "click_128_60s.beats", 30, 1, 0, 4242, mezz_frames)
    out = work / "bench_master.mp4"
    r_s: list[float] = []
    rv_s: list[float] = []
    rss: list[float] = []
    steals: list[float] = []
    discarded = 0
    for _ in range(n_render):
        res, steal, attempts = bench.run_quiet(
            lambda: build_render(tools, codec, plan, mezz_paths, out)
        )
        discarded += attempts - 1
        t = time.monotonic()
        v = verify.verify_render(tools, plan, out, palette)
        vt = time.monotonic() - t
        if not v["pass"]:
            raise FfError("bench render failed verification")
        r_s.append(res.wall_s)
        rv_s.append(res.wall_s + vt)
        rss.append((res.rss_kb or 0) / 1024.0)
        steals.append(steal)
    probe = verify.probe_video(tools, out)
    m_s: list[float] = []
    mv_s: list[float] = []
    mrss: list[float] = []
    msteal: list[float] = []
    for k in range(n_remux):
        ext = AUDIO_EXTS[k % len(AUDIO_EXTS)]
        src = audio["128"][ext]
        aac = remux.is_aac_lc(tools, src)
        rout = work / "bench_remux.mp4"

        def go_r(src: Path = src, rout: Path = rout, aac: bool = aac) -> Any:
            return remux.build_remux(tools, out, src, plan.t0, plan.total_frames, rout, aac)

        res, steal, attempts = bench.run_quiet(go_r)
        discarded += attempts - 1
        t = time.monotonic()
        rv = remux.verify_remux(
            tools, probe["packet_hashes"], probe["pts"], rout, src, plan.t0, plan.total_frames, aac
        )
        vt = time.monotonic() - t
        if not rv["pass"]:
            raise FfError("bench remux failed verification")
        m_s.append(res.wall_s)
        mv_s.append(res.wall_s + vt)
        mrss.append((res.rss_kb or 0) / 1024.0)
        msteal.append(steal)
    return {
        "discarded_runs_steal_gt_5pct": discarded,
        "render": {
            "render_s": bench.summarize(r_s),
            "verified_s": bench.summarize(rv_s),
            "rss_mb": float(np.max(rss)),
            "steal_pct": float(np.max(steals)),
            "n_shots": len(plan.shots),
        },
        "remux": {
            "remux_s": bench.summarize(m_s),
            "verified_s": bench.summarize(mv_s),
            "rss_mb": float(np.max(mrss)),
            "steal_pct": float(np.max(msteal)),
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ffmpeg", required=True)
    ap.add_argument("--ffprobe", default=None)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--work", type=Path, default=None)
    ap.add_argument("--synth", type=Path, default=HOME / "data/synth")
    ap.add_argument("--clips", type=Path, default=HOME / "data/synth/clips")
    ap.add_argument("--vcodec", default="auto")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--only", nargs="*", default=None, help="case ids (prefix match)")
    ap.add_argument("--no-remux", action="store_true")
    ap.add_argument("--no-bench", action="store_true")
    ap.add_argument("--no-progress-test", action="store_true")
    ap.add_argument("--bench-renders", type=int, default=10)
    ap.add_argument("--bench-remuxes", type=int, default=20)
    a = ap.parse_args(argv)

    ffmpeg = str(Path(a.ffmpeg).resolve())
    ffprobe = a.ffprobe or str(Path(ffmpeg).with_name("ffprobe"))
    tools = Tools(ffmpeg, ffprobe)
    ver = version_line(ffmpeg)
    tag = ver.split()[2] if len(ver.split()) > 2 else "unknown"
    work = a.work or HOME / "data/results/renders" / tag
    work.mkdir(parents=True, exist_ok=True)
    codec = pick_vcodec(tools, a.vcodec)
    print(f"ffmpeg: {ver}\nvcodec: {codec}\nwork: {work}", flush=True)

    clips = make_clips(tools, codec, a.clips)
    audio = {
        t: make_audio_sources(tools, a.synth / f"click_{t}_60s.wav", a.clips / "audio")
        for t in BPM_TAGS
    }
    inputs = {
        "clips": {n: sha256_file(p) for n, p in clips.items()},
        "audio": {f"{t}.{e}": sha256_file(p) for t, d in audio.items() for e, p in d.items()},
    }

    t_run = bench.cpu_times()
    mezz_rows, mezz_map = mezz_stage(tools, codec, clips, work)
    print(f"mezz {sum(r['pass'] for r in mezz_rows)}/{len(mezz_rows)} PASS", flush=True)
    for r in mezz_rows:
        if not r["pass"]:
            print(f"  mezz FAIL {r['name']}: {r['failed']}")
    solid = [mezz_map[s.name] for s in clip_specs() if s.source == "color"]
    solid_frames = [r["nb_frames"] for r in mezz_rows if r["name"].startswith("solid_")]
    palette = verify.measure_palette(tools, solid)
    pmin = verify.min_pair_distance(palette)
    print(f"measured palette min pairwise RGB distance: {pmin:.1f}", flush=True)
    if pmin < 60:
        raise FfError("palette not separable after encode")

    allc = cases(a.n)
    sel = [c for c in allc if a.only is None or any(c["id"].startswith(p) for p in a.only)]
    renders, remuxes = run_cases(
        tools, codec, work, a.synth, audio, solid, solid_frames, palette, sel, not a.no_remux
    )

    prog: dict[str, Any] = {}
    if not a.no_progress_test:
        plan = build_plan("PROG", a.synth / "click_128_60s.beats", 30, 1, 0, 77, solid_frames)
        prog = progress_test(tools, codec, work, plan, solid, palette)
        print(
            "progress test: "
            + json.dumps(
                {k: (v.get("works") if isinstance(v, dict) else v) for k, v in prog.items()}
            ),
            flush=True,
        )

    benchres: dict[str, Any] = {}
    if not a.no_bench and not a.no_remux:
        benchres = bench_stage(
            tools,
            codec,
            work,
            a.synth,
            audio,
            solid,
            solid_frames,
            palette,
            a.bench_renders,
            a.bench_remuxes,
        )

    run_steal = bench.steal_pct(t_run, bench.cpu_times())
    r_pass = sum(1 for r in renders if r["verify"]["pass"])
    m_pass = sum(1 for r in remuxes if r["verify"]["pass"])
    mz_pass = sum(1 for r in mezz_rows if r["pass"])
    dev1 = sum(len(r["verify"]["cuts"]["deviations_1f"]) for r in renders)
    result = {
        "schema": SCHEMA,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ffmpeg": {
            "path": ffmpeg,
            "version": ver,
            "ffprobe": ffprobe,
            "ffprobe_version": version_line(ffprobe),
            "vcodec": codec,
        },
        "host": {**host_info(), "run_steal_pct": run_steal},
        "inputs": inputs,
        "mezz": mezz_rows,
        "palette_min_distance": pmin,
        "renders": renders,
        "remuxes": remuxes,
        "progress_test": prog,
        "bench": benchres,
        "summary": {
            "render_pass": r_pass,
            "render_total": len(renders),
            "remux_pass": m_pass,
            "remux_total": len(remuxes),
            "mezz_pass": mz_pass,
            "mezz_total": len(mezz_rows),
            "deviations_1f": dev1,
        },
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=1), encoding="utf-8")

    print(f"mezz {mz_pass}/{len(mezz_rows)} PASS")
    print(f"render {r_pass}/{len(renders)} {'PASS' if r_pass == len(renders) else 'FAIL'}")
    if not a.no_remux:
        print(f"remux {m_pass}/{len(remuxes)} {'PASS' if m_pass == len(remuxes) else 'FAIL'}")
    print(f"1-frame deviations: {dev1}")
    print(timing_table(renders, remuxes, benchres))
    print(f"run %steal: {run_steal:.2f}")
    ok = (
        r_pass == len(renders)
        and mz_pass == len(mezz_rows)
        and (a.no_remux or m_pass == len(remuxes))
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

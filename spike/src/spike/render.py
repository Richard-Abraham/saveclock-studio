"""Final render -> silent master (ARCHITECTURE 11 "Final render" template)."""

from __future__ import annotations

from pathlib import Path

from spike.ffwrap import MP4_FMT, RunResult, Tools, ffmpeg_cmd, run
from spike.plan import Plan
from spike.vcodec import render_encode

THREADS = "4"


def filter_graph(plan: Plan) -> str:
    """trim by FRAME index (never seconds), concat, null."""
    parts: list[str] = []
    for k, shot in enumerate(plan.shots):
        s, e = shot.in_frame, shot.in_frame + shot.length
        parts.append(f"[{k}:v]trim=start_frame={s}:end_frame={e},setpts=PTS-STARTPTS[v{k}]")
    labels = "".join(f"[v{k}]" for k in range(len(plan.shots)))
    parts.append(f"{labels}concat=n={len(plan.shots)}:v=1:a=0[vc]")
    parts.append("[vc]null[vout]")
    return ";".join(parts)


def render_cmd(
    tools: Tools,
    codec: str,
    plan: Plan,
    mezz_paths: list[Path],
    out: Path,
    progress: str | None = None,
) -> list[str]:
    ins: list[str] = []
    for shot in plan.shots:
        ins += ["-f", MP4_FMT, "-i", str(mezz_paths[shot.clip])]
    prog = ["-progress", progress, "-nostats"] if progress else []
    return ffmpeg_cmd(
        tools,
        *ins,
        *("-filter_complex", filter_graph(plan)),
        *("-map", "[vout]", "-an"),
        *render_encode(codec),
        *("-r", "30", "-fps_mode", "cfr", "-g", "60", "-video_track_timescale", "30000"),
        *("-threads", THREADS),
        *("-frames:v", str(plan.total_frames)),
        *prog,
        *("-movflags", "+faststart", "-f", "mp4", str(out)),
    )


def build_render(
    tools: Tools,
    codec: str,
    plan: Plan,
    mezz_paths: list[Path],
    out: Path,
    progress: str | None = None,
) -> RunResult:
    return run(render_cmd(tools, codec, plan, mezz_paths, out, progress), 600, rss=True)

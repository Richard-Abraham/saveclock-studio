"""Render test media: four solid portrait clips of unmistakable, well separated colours (so every
cut of a render is a measurable colour change), a pixel-per-frame decoder, and a palette matcher.

Nothing here is committed media: every clip is generated with the pinned FFmpeg. The colours are
the ones of `make fake-stock`, the single owner of them (`eval/scripts/make_fake_stock.py`).
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from saveclock.adapters.ffmpeg import MP4_FMT, Tools, build_mezz, ffmpeg_cmd, render_cmd, run
from saveclock.domain.edit_plan import EditPlan
from saveclock.domain.windows import Window
from tests.factories.stock import fake_stock
from tests.unit.domain.plan_support import inputs, one_section, pool, uniform_grid

Rgb = npt.NDArray[np.float64]
SOLID = ("red", "green", "blue", "yellow")
COLOURS = {
    "red": fake_stock.RED,
    "green": fake_stock.GREEN,
    "blue": fake_stock.BLUE,
    "yellow": fake_stock.YELLOW,
}


def solid_stock(tools: Tools, out_dir: Path) -> Path:
    """`out_dir` holds red, green, blue and yellow portrait clips and the `index.json` FAKE_STOCK
    serves: a pool of exactly four distinct colours."""
    out_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for name in SOLID:
        spec = fake_stock.FakeClip(f"{name}_portrait", "720x1280", ((COLOURS[name], 6.0),))
        path = out_dir / f"{spec.name}.mp4"
        if not path.exists():
            fake_stock.make_clip(tools, spec, path)
        index.append(
            {"name": spec.name, "width": 720, "height": 1280, "duration_s": 6.0, "fps": 30}
        )
    (out_dir / "index.json").write_text(json.dumps({"clips": index}))
    return out_dir


def decode_colours(tools: Tools, path: Path) -> Rgb:
    """One area-averaged pixel per frame (an output pipe is not an input protocol, so
    `-protocol_whitelist file` stands): `(n_frames, 3)` RGB."""
    cmd = ffmpeg_cmd(
        tools,
        *("-f", MP4_FMT, "-i", str(path), "-map", "0:v:0"),
        *("-vf", "scale=1:1:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"),
    )
    raw = run(cmd, 300).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.float64)


def measured_colour(tools: Tools, path: Path) -> Rgb:
    """The median colour of a solid clip (robust to the YUV/RGB conversion)."""
    return np.median(decode_colours(tools, path), axis=0)


def nearest(colours: Rgb, palette: Rgb) -> list[int]:
    """Index of the closest palette colour for every frame."""
    d = np.linalg.norm(colours[:, None, :] - palette[None, :, :], axis=2)
    return [int(i) for i in np.argmin(d, axis=1)]


def changes(labels: list[int]) -> list[int]:
    """Frame indices where the label differs from the previous frame."""
    return [i for i in range(1, len(labels)) if labels[i] != labels[i - 1]]


@dataclass(frozen=True)
class Rendered:
    plan: EditPlan
    master: Path
    palette: Rgb  # the measured colour of each pool clip, in pool order


def render_plan(
    tools: Tools,
    tmp: Path,
    clips_dir: Path,
    *,
    bpm: float = 128.0,
    seconds: int = 15,
    label: str = "e3",
    threads: int = 2,
) -> Rendered:
    """Plan a click track over four solid mezzanines (one pool clip per colour, so adjacent shots
    never share a colour) and render it with the production command. Returns the plan, the
    master and the palette measured from the mezzanines."""
    from saveclock.domain.planner import build_plan

    clips = pool(len(SOLID), frames=162)
    plan = build_plan(
        inputs(uniform_grid(bpm), one_section(label), seconds=seconds, clips=clips)
    ).plan
    mezz: dict[str, Path] = {}
    for i, name in enumerate(SOLID):
        out = tmp / f"mezz_{name}.mp4"
        build_mezz(tools, clips_dir / f"{name}_portrait.mp4", Window(0.2, 5.4), out)
        mezz[clips[i].provider_id] = out
    paths = [mezz[c.clip.provider_id] for c in plan.cuts]
    master = tmp / "master.mp4"
    cmd = render_cmd(tools, plan, paths, master, progress=tmp / "progress.txt", threads=threads)
    run(cmd, 300)
    palette = np.asarray([measured_colour(tools, mezz[c.provider_id]) for c in clips])
    return Rendered(plan, master, palette)

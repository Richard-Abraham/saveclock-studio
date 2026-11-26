"""Fake stock clips made with FFmpeg's lavfi (port of the spike's synth_clips.py).

Songs and stock clips are never committed: every test clip is generated here, from solid colours
with a fine grid on top (a flat frame would fail the blur check) and distinct, well separated RGB
values. `lavfi` is used only on these generated sources, never on untrusted input (SEC-011).

usage (from services/api): python ../../eval/scripts/make_fake_stock.py <out-dir>
prints the 8 clip names, one per line.
"""

import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from saveclock.adapters.ffmpeg import Tools, ffmpeg_cmd, run

RED, GREEN, BLUE, YELLOW = "0xd02020", "0x20c020", "0x2020d0", "0xe0d020"
GRADIENT_S = 4.0
GRID = "drawgrid=w=48:h=48:t=2:c=white@0.6"
ENCODE = ("-c:v", "libx264", "-preset", "ultrafast", "-crf", "44", "-g", "600", "-an")


@dataclass(frozen=True)
class FakeClip:
    name: str
    size: str  # WxH
    segments: tuple[tuple[str, float], ...]  # (colour, seconds); more than one = hard cuts
    blur: bool = False
    gradient: bool = False
    fps: int = 30

    @property
    def seconds(self) -> float:
        return GRADIENT_S if self.gradient else sum(s for _, s in self.segments)


SPECS: tuple[FakeClip, ...] = (
    FakeClip("red_portrait", "720x1280", ((RED, 6.0),)),
    FakeClip("green_portrait", "720x1280", ((GREEN, 6.0),)),
    FakeClip("blue_portrait", "720x1280", ((BLUE, 6.0),)),
    FakeClip("gradient_portrait", "720x1280", (), gradient=True),
    # one hard cut at 4.0 s: both halves are cut-free windows of 4 s
    FakeClip("cut_long_portrait", "720x1280", ((RED, 4.0), (BLUE, 4.0))),
    # hard cuts every 2 s: no cut-free window of 3 s exists
    FakeClip("cut_short_portrait", "720x1280", ((RED, 2.0), (BLUE, 2.0), (RED, 2.0), (BLUE, 2.0))),
    FakeClip("landscape", "1280x720", ((YELLOW, 6.0),)),
    FakeClip("small_portrait", "480x854", ((GREEN, 6.0),)),
)
# made on demand by the tests (not part of `make fake-stock`)
EXTRA: dict[str, FakeClip] = {
    "short_portrait": FakeClip("short_portrait", "720x1280", ((RED, 2.0),)),
    "blurry_portrait": FakeClip("blurry_portrait", "720x1280", ((RED, 6.0),), blur=True),
}


def make_clip(tools: Tools, spec: FakeClip, out: Path) -> Path:
    size = spec.size
    if spec.gradient:
        inputs = ["-f", "lavfi", "-i", f"gradients=s={size}:r={spec.fps}:d={GRADIENT_S}:speed=0.01:seed=7"]
        chain = f"{GRID},format=yuv420p"
    else:
        inputs = []
        for colour, seconds in spec.segments:
            inputs += ["-f", "lavfi", "-i", f"color=c={colour}:s={size}:r={spec.fps}:d={seconds}"]
        n = len(spec.segments)
        concat = "".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]"
        chain = f"{concat};[v]{GRID}"
        if spec.blur:
            chain += ",gblur=sigma=25"
        chain += ",format=yuv420p"
    filt = ["-vf", chain] if spec.gradient else ["-filter_complex", chain]
    cmd = ffmpeg_cmd(
        tools, *inputs, *filt, *ENCODE, "-movflags", "+faststart", "-f", "mp4", str(out)
    )
    run(cmd, 120)
    return out


def make_all(tools: Tools, out_dir: Path, extra: Iterable[FakeClip] = ()) -> list[Path]:
    """The clips plus `index.json` (the metadata FAKE_STOCK serves; known from the specs)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths, index = [], []
    for spec in (*SPECS, *extra):
        path = out_dir / f"{spec.name}.mp4"
        if not path.exists():
            make_clip(tools, spec, path)
        paths.append(path)
        width, height = (int(v) for v in spec.size.split("x"))
        index.append(
            {
                "name": spec.name,
                "width": width,
                "height": height,
                "duration_s": spec.seconds,
                "fps": spec.fps,
            }
        )
    (out_dir / "index.json").write_text(json.dumps({"clips": index}, indent=1))
    return paths


if __name__ == "__main__":
    if len(sys.argv) != 2:  # noqa: PLR2004
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    root = Path(__file__).resolve().parents[2] / ".data" / "ffmpeg"
    made = make_all(Tools(str(root / "ffmpeg"), str(root / "ffprobe")), Path(sys.argv[1]))
    for p in made:
        print(p.name)

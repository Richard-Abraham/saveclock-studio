"""Which stock clips are usable: pure checks on provider metadata and on the probed file.

Limits: SEC-019 (100 MB), ARCH §11 (3 to 60 s, one video stream, width >= 720).
"""

from dataclasses import dataclass
from enum import StrEnum

MIN_WIDTH = 720
MIN_FPS = 24
MIN_DURATION_S = 3
MAX_DURATION_S = 60
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
MAX_WINDOW_S = 15
MIN_WINDOW_S = 3
BLUR_VAR_MIN = 40.0  # hypothesis: tuned by the owner's eyes; QM-040/041 are not measured


class RejectReason(StrEnum):
    NOT_PORTRAIT = "not_portrait"
    TOO_SMALL = "too_small"
    LOW_FPS = "low_fps"
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    TOO_LARGE = "too_large"
    FFPROBE_FAILED = "ffprobe_failed"
    NO_CUT_FREE_WINDOW = "no_cut_free_window"
    BLURRY = "blurry"


@dataclass(frozen=True)
class ClipMeta:
    """What a provider or ffprobe says about a clip; `None` means unknown (not checked)."""

    width: int
    height: int
    duration_s: float
    fps: float | None = None
    size_bytes: int | None = None


def check_candidate(meta: ClipMeta) -> RejectReason | None:
    """The first rule a clip breaks, in the order cheapest and most telling first."""
    if meta.height <= meta.width:
        return RejectReason.NOT_PORTRAIT
    if meta.width < MIN_WIDTH:
        return RejectReason.TOO_SMALL
    if meta.fps is not None and meta.fps < MIN_FPS:
        return RejectReason.LOW_FPS
    if meta.duration_s < MIN_DURATION_S:
        return RejectReason.TOO_SHORT
    if meta.duration_s > MAX_DURATION_S:
        return RejectReason.TOO_LONG
    if meta.size_bytes is not None and meta.size_bytes > MAX_DOWNLOAD_BYTES:
        return RejectReason.TOO_LARGE
    return None


def is_blurry(laplacian_variance: float) -> bool:
    return laplacian_variance < BLUR_VAR_MIN

"""The per-render verification decisions (QUALITY §7), pure over measurements.

The adapters measure (ffprobe, decoded gray frames, filter stderr); this module decides. Every
check has an id (the QM number), a level (`BLOCK` fails the render, `WARN` is only recorded) and an
outcome. A check that can fail at two levels (black frames) carries the level it failed at.
Constants marked `hypothesis:` are tuning candidates; QUALITY.md owns them, change it first.
"""

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from saveclock.domain.framemath import FPS
from saveclock.domain.video_checks import video_checks

CUT_WINDOW = 3  # frames either side of a planned cut searched for the difference peak
MEDIAN_HALF = 20  # the local median is taken over d[c - 20 : c + 20]
PEAK_RATIO = 4.0  # peak must exceed this multiple of the local median
PEAK_FLOOR = 4.0  # hypothesis: mean abs gray difference (0..255) below which no peak counts
BLOCK_CUT_ERROR = 1  # |offset| above this blocks
PRESENCE_MIN = 0.98  # QM-065: share of cuts that show a peak at all
BLACK_WARN_FRAMES, BLACK_BLOCK_FRAMES = 3, 6  # hypothesis (QM-070)
FREEZE_BLOCK_S = 1.5  # hypothesis (QM-071)
MAX_SIZE_BYTES = 250 * 1_000_000  # hypothesis: 250 MB (QM-076)
MAX_BITRATE_BPS = 25_000_000  # hypothesis: 25 Mbit/s (QM-076)
TRUE_PEAK_MAX_DBTP = -0.5  # hypothesis (QM-073)
INTEGRATED_MIN_LUFS = -26.0  # hypothesis (QM-073)
SILENCE_MAX_S = 2.0  # QM-074: a silence this long that the source segment does not have
TRANSCODE_RATE_HZ = 48000  # the transcode path writes AAC-LC at this rate
AAC_FRAME_S = 1024 / TRANSCODE_RATE_HZ  # 21.333 ms
OFFSET_LIMIT_S = 1 / FPS  # 33.3 ms (QM-067 Block)
OFFSET_AIM_S = 1 / (2 * FPS)  # 16.7 ms (QM-067 Warn)


class Level(StrEnum):
    BLOCK = "block"
    WARN = "warn"


@dataclass(frozen=True)
class CheckResult:
    id: str
    level: Level
    ok: bool
    detail: str = ""

    def as_json(self) -> dict[str, Any]:
        return {"id": self.id, "level": self.level.value, "ok": self.ok, "detail": self.detail}


def failed_blocks(results: Sequence[CheckResult]) -> list[CheckResult]:
    return [r for r in results if not r.ok and r.level is Level.BLOCK]


# --- the master -----------------------------------------------------------------------------------


def master_checks(probe: dict[str, Any], total_frames: int) -> list[CheckResult]:
    """QM-060 to 063 and 077 over the ffprobe result: plan 005's `video_checks`, as results."""
    out: list[CheckResult] = []
    for c in video_checks(probe, total_frames):
        qm, _, rest = c.name.partition(" ")
        out.append(CheckResult(qm, Level.BLOCK, c.ok, f"{rest}: {c.detail}" if c.detail else rest))
    return out


def playable_check(stderr: str) -> CheckResult:
    """QM-075: a full decode to null must print nothing (the runner uses `-loglevel error`)."""
    text = stderr.strip()
    return CheckResult("QM-075", Level.BLOCK, not text, text[:200])


def size_bitrate_warn(size_bytes: int, duration_s: float) -> CheckResult:
    """QM-076 (Warn): over 250 MB or 25 Mbit/s."""
    bitrate = size_bytes * 8 / duration_s if duration_s > 0 else 0.0
    ok = size_bytes <= MAX_SIZE_BYTES and bitrate <= MAX_BITRATE_BPS
    return CheckResult("QM-076", Level.WARN, ok, f"{size_bytes} bytes, {bitrate / 1e6:.1f} Mbit/s")


# --- cuts (QM-064/065/066) ------------------------------------------------------------------------


@dataclass(frozen=True)
class CutObservation:
    frame: int
    offset: int | None  # None: no observable peak


@dataclass(frozen=True)
class CutReport:
    cuts: list[CutObservation]

    @property
    def observed(self) -> list[int]:
        return [c.offset for c in self.cuts if c.offset is not None]

    @property
    def max_error(self) -> int:
        return max((abs(o) for o in self.observed), default=0)

    @property
    def presence(self) -> float:
        return len(self.observed) / len(self.cuts) if self.cuts else 1.0

    def checks(self) -> list[CheckResult]:
        n_unobservable = len(self.cuts) - len(self.observed)
        return [
            CheckResult(
                "QM-064",
                Level.BLOCK,
                self.max_error <= BLOCK_CUT_ERROR,
                f"max |offset| {self.max_error} frame(s) over {len(self.observed)} cuts",
            ),
            CheckResult("QM-064", Level.WARN, self.max_error == 0, f"max {self.max_error}"),
            CheckResult(
                "QM-065",
                Level.WARN,
                self.presence >= PRESENCE_MIN,
                f"{n_unobservable} of {len(self.cuts)} cuts without a visible peak",
            ),
        ]


def _local_median(diffs: Sequence[float], centre: int) -> float:
    window = diffs[max(0, centre - MEDIAN_HALF) : centre + MEDIAN_HALF]
    return statistics.median(window) if window else 0.0


def _is_peak(value: float, median: float) -> bool:
    return value > PEAK_RATIO * median and value > PEAK_FLOOR


def detect_cuts(diffs: Sequence[float], planned_frames: Sequence[int]) -> CutReport:
    """`diffs[f]` is the mean absolute gray difference between frame f and f - 1.

    For every planned cut frame c the peak of `diffs[c - 3 : c + 4]` must exceed 4x the local
    median and the floor; its distance from c is the offset (expected 0). A cut with no such peak
    is unobservable: it counts for QM-065, it is never a Block on its own.
    """
    out: list[CutObservation] = []
    for c in planned_frames:
        lo = max(0, c - CUT_WINDOW)
        window = diffs[lo : c + CUT_WINDOW + 1]
        if not window:
            out.append(CutObservation(c, None))
            continue
        peak = lo + max(range(len(window)), key=lambda i: window[i])
        observed = _is_peak(diffs[peak], _local_median(diffs, c))
        out.append(CutObservation(c, peak - c if observed else None))
    return CutReport(out)


def unplanned_candidates(diffs: Sequence[float], planned_frames: Sequence[int]) -> list[int]:
    """Frames where the difference signal peaks like a cut (a strict local maximum over the ratio
    and the floor) and that are not within one frame of a planned cut."""
    found: list[int] = []
    for f in range(1, len(diffs)):
        right = diffs[f + 1] if f + 1 < len(diffs) else 0.0
        peak = diffs[f] >= diffs[f - 1] and diffs[f] > right
        if (
            peak
            and _is_peak(diffs[f], _local_median(diffs, f))
            and all(abs(f - c) > 1 for c in planned_frames)
        ):
            found.append(f)
    return found


def confirmed(candidates: Sequence[int], detected_frames: Sequence[int]) -> list[int]:
    """The candidates the scene detector also reports (within one frame): both must agree."""
    return [f for f in candidates if any(abs(f - d) <= 1 for d in detected_frames)]


def unplanned_cuts(
    diffs: Sequence[float], planned_frames: Sequence[int], detected_frames: Sequence[int]
) -> list[int]:
    return confirmed(unplanned_candidates(diffs, planned_frames), detected_frames)


def unplanned_check(frames: Sequence[int]) -> CheckResult:
    return CheckResult("QM-066", Level.WARN, not frames, f"unplanned cuts at {list(frames)[:5]}")


# --- black and frozen frames (QM-070/071) ---------------------------------------------------------


def black_report(durations_frames: Sequence[int]) -> CheckResult:
    """Block for a run of 6 frames or more, Warn for 3 to 5 (hypothesis)."""
    longest = max(durations_frames, default=0)
    if longest >= BLACK_BLOCK_FRAMES:
        return CheckResult("QM-070", Level.BLOCK, False, f"{longest} black frames in a row")
    if longest >= BLACK_WARN_FRAMES:
        return CheckResult("QM-070", Level.WARN, False, f"{longest} black frames in a row")
    return CheckResult("QM-070", Level.BLOCK, True, f"longest run {longest}")


def freeze_report(durations_s: Sequence[float]) -> CheckResult:
    """Any freeze (the detector's minimum is 0.5 s) warns; 1.5 s or more blocks (hypothesis)."""
    longest = max(durations_s, default=0.0)
    if longest >= FREEZE_BLOCK_S:
        return CheckResult("QM-071", Level.BLOCK, False, f"frozen for {longest:.2f} s")
    if longest > 0:
        return CheckResult("QM-071", Level.WARN, False, f"frozen for {longest:.2f} s")
    return CheckResult("QM-071", Level.BLOCK, True, "no freeze")


# --- Mode A (QM-067/068/073/074/077/087) ----------------------------------------------------------


@dataclass(frozen=True)
class RemuxFacts:
    """What the adapters measured on the remuxed file."""

    stream_kinds: Sequence[str]
    audio_codec: str
    audio_profile: str | None
    audio_sample_rate: int | None
    aac_copy: bool
    video_hashes: Sequence[str]
    master_hashes: Sequence[str]
    audio_run_in_source: bool | None  # the copy path: the output packets are a run of the source's
    audio_duration_s: float
    duration_s: float
    offset_start_s: float
    offset_end_s: float
    drift_per_60_s: float
    true_peak_dbtp: float | None
    integrated_lufs: float | None
    out_silences_s: Sequence[float]
    source_silences_s: Sequence[float]


def remux_checks(f: RemuxFacts) -> list[CheckResult]:
    kinds = sorted(f.stream_kinds)
    out = [
        CheckResult("QM-077", Level.BLOCK, kinds == ["audio", "video"], f"streams {kinds}"),
        CheckResult(
            "QM-087",
            Level.BLOCK,
            f.audio_codec == "aac" and f.audio_profile == "LC",
            f"audio {f.audio_codec}/{f.audio_profile}",
        ),
        CheckResult(
            "QM-087",
            Level.BLOCK,
            list(f.video_hashes) == list(f.master_hashes),
            f"video packets {len(f.video_hashes)} vs {len(f.master_hashes)}",
        ),
    ]
    if f.aac_copy:
        out.append(
            CheckResult(
                "QM-087",
                Level.BLOCK,
                bool(f.audio_run_in_source),
                "audio packets are the source's (stream copy)",
            )
        )
    else:
        out.append(
            CheckResult(
                "QM-087",
                Level.BLOCK,
                f.audio_sample_rate == TRANSCODE_RATE_HZ,
                f"{f.audio_sample_rate} Hz",
            )
        )
    out += [
        CheckResult(
            "QM-063",
            Level.BLOCK,
            abs(f.audio_duration_s - f.duration_s) <= AAC_FRAME_S + 1e-3,
            f"audio {f.audio_duration_s:.4f} s vs {f.duration_s:.4f} s",
        )
    ]
    for label, off in (("t~1 s", f.offset_start_s), ("t~end-1 s", f.offset_end_s)):
        out.append(
            CheckResult(
                "QM-067", Level.BLOCK, abs(off) <= OFFSET_LIMIT_S, f"{off * 1e3:.2f} ms {label}"
            )
        )
        out.append(
            CheckResult(
                "QM-067", Level.WARN, abs(off) <= OFFSET_AIM_S, f"{off * 1e3:.2f} ms {label}"
            )
        )
    out.append(
        CheckResult(
            "QM-068",
            Level.BLOCK,
            abs(f.drift_per_60_s) <= OFFSET_LIMIT_S,
            f"{f.drift_per_60_s * 1e3:.2f} ms per 60 s",
        )
    )
    loud_ok = (f.true_peak_dbtp is None or f.true_peak_dbtp <= TRUE_PEAK_MAX_DBTP) and (
        f.integrated_lufs is None or f.integrated_lufs >= INTEGRATED_MIN_LUFS
    )
    out.append(
        CheckResult(
            "QM-073", Level.WARN, loud_ok, f"{f.true_peak_dbtp} dBTP, {f.integrated_lufs} LUFS"
        )
    )
    new_silences = [s for s in f.out_silences_s if s >= SILENCE_MAX_S]
    source_silences = [s for s in f.source_silences_s if s >= SILENCE_MAX_S]
    out.append(
        CheckResult(
            "QM-074",
            Level.WARN,
            len(new_silences) <= len(source_silences),
            f"{len(new_silences)} silences over {SILENCE_MAX_S} s ({len(source_silences)} in src)",
        )
    )
    return out

"""Beat metrics, UNTRIMMED (QUALITY 14.1).

Never call ``mir_eval.beat.evaluate()``: it trims the first 5 s (``trim_beats`` default 5.0).
Here the individual metric functions are called on the full arrays (equivalent to
``min_beat_time=0``). Parameters (mir_eval 0.8.2 defaults): F window 0.07 s, Cemgil sigma 0.04,
continuity thresholds 0.175, information-gain bins 41.
"""

from __future__ import annotations

import mir_eval
import mir_eval.beat
import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]

F_WINDOW_S = 0.07
OCTAVE_RATIO_TOL = 0.08
Result = dict[str, float | str | None]


def octave_error(ref: FloatArray, est: FloatArray) -> float | None:
    """1.0 if the median inter-beat interval is ~2x or ~0.5x the reference, else 0.0.

    Per-track flag; the mean over tracks is the octave-error rate. None if too few beats.
    """
    if len(ref) < 2 or len(est) < 2:
        return None
    ratio = float(np.median(np.diff(est)) / np.median(np.diff(ref)))
    return float(any(abs(ratio / r - 1.0) <= OCTAVE_RATIO_TOL for r in (2.0, 0.5)))


def mean_signed_offset_ms(ref: FloatArray, est: FloatArray) -> float | None:
    """Mean of (nearest estimate - reference) in ms over reference beats matched within the window."""
    if len(ref) == 0 or len(est) == 0:
        return None
    d = est[None, :] - ref[:, None]
    off = d[np.arange(len(ref)), np.argmin(np.abs(d), axis=1)]
    off = off[np.abs(off) <= F_WINDOW_S]
    return float(off.mean() * 1000.0) if len(off) else None


def evaluate_track(
    ref: FloatArray,
    est: FloatArray,
    ref_down: FloatArray | None = None,
    est_down: FloatArray | None = None,
) -> Result:
    """Per-track metrics on untrimmed arrays."""
    f = mir_eval.beat.f_measure(ref, est, f_measure_threshold=F_WINDOW_S)
    cmlc, cmlt, amlc, amlt = mir_eval.beat.continuity(ref, est)
    ig = mir_eval.beat.information_gain(ref, est)
    out: Result = {
        "mir_eval_version": mir_eval.__version__,
        "f_measure": float(f),
        "cmlc": float(cmlc),
        "cmlt": float(cmlt),
        "amlc": float(amlc),
        "amlt": float(amlt),
        "information_gain": float(ig),
        "octave_error": octave_error(ref, est),
        "mean_signed_offset_ms": mean_signed_offset_ms(ref, est),
        "downbeat_f1": None,
    }
    if ref_down is not None and est_down is not None:
        out["downbeat_f1"] = float(
            mir_eval.beat.f_measure(ref_down, est_down, f_measure_threshold=F_WINDOW_S)
        )
    return out

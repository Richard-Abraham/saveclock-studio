"""Signal features with numpy and scipy only (P4-9: no librosa, its numba JIT needs a cache).

Imported by the worker's analysis service only; `soundfile` and `scipy` are imported inside the
functions that need them so importing this module costs nothing in the API image.
shortcut: spectral-flux onsets and an autocorrelation tempo, about 80 lines; upgrade only if a
metric needs a feature numpy cannot give cheaply.
"""

from itertools import pairwise
from pathlib import Path

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float32]
CURVE_HZ = 10
N_FFT = 1024
HOP = 512
CHUNK_FRAMES = 4096
PEAK_BUCKETS = 2000
TEMPO_RANGE_BPM = (40.0, 240.0)
MATCH_S = 0.05  # an onset counts for a beat within +-50 ms
SILENT_DB = -60.0


def decode_mono(path: Path) -> tuple[FloatArray, int]:
    """The canonical FLAC as a mono float32 array (down-mix in numpy; no temp file)."""
    import soundfile

    data, sr = soundfile.read(str(path), dtype="float32", always_2d=True)
    return np.ascontiguousarray(data.mean(axis=1), dtype=np.float32), int(sr)


def rms_db(signal: FloatArray, sr: int) -> list[float]:
    """RMS in dBFS at 10 Hz (one value per 100 ms, non-overlapping)."""
    step = sr // CURVE_HZ
    n = len(signal) // step
    if n == 0:
        return []
    frames = signal[: n * step].reshape(n, step).astype(np.float64)
    rms = np.sqrt((frames**2).mean(axis=1))
    return [float(v) for v in 20.0 * np.log10(np.maximum(rms, 1e-9))]


def waveform_peaks(signal: FloatArray, buckets: int = PEAK_BUCKETS) -> list[float]:
    """Per-bucket absolute peak, 3 decimals, at most `buckets` points."""
    n = min(buckets, len(signal))
    if n == 0:
        return []
    edges = np.linspace(0, len(signal), n + 1).astype(int)
    peaks = np.maximum.reduceat(np.abs(signal), edges[:-1])
    return [round(float(p), 3) for p in peaks]


def onset_envelope(signal: FloatArray, sr: int) -> tuple[npt.NDArray[np.float64], float]:
    """Half-wave rectified spectral flux of the log magnitude; returns (envelope, frames/s)."""
    window = np.hanning(N_FFT).astype(np.float32)
    n_frames = max(0, (len(signal) - N_FFT) // HOP + 1)
    flux = np.zeros(n_frames, dtype=np.float64)
    prev: npt.NDArray[np.float64] | None = None
    for start in range(0, n_frames, CHUNK_FRAMES):
        stop = min(start + CHUNK_FRAMES, n_frames)
        idx = np.arange(start, stop)[:, None] * HOP + np.arange(N_FFT)[None, :]
        mag = np.abs(np.fft.rfft(signal[idx] * window, axis=1))
        log = np.log1p(100.0 * mag).astype(np.float64)
        shifted = np.vstack([prev if prev is not None else log[:1], log[:-1]])
        flux[start:stop] = np.maximum(log - shifted, 0.0).sum(axis=1)
        prev = log[-1:]
    return flux, sr / HOP


def onset_tempo(env: npt.NDArray[np.float64], rate: float) -> float | None:
    """Tempo (BPM) from the autocorrelation of the onset envelope, independent of the beat model."""
    if len(env) < rate * 4:
        return None
    x = env - env.mean()
    if not x.any():
        return None
    spectrum = np.fft.rfft(x, 2 * len(x))
    acf = np.fft.irfft(spectrum * np.conj(spectrum))[: len(x)]
    lo, hi = (int(rate * 60.0 / bpm) for bpm in reversed(TEMPO_RANGE_BPM))
    if hi <= lo or hi >= len(acf):
        return None
    lag = lo + int(np.argmax(acf[lo : hi + 1]))
    return float(60.0 * rate / lag)


def _peak_near(env: npt.NDArray[np.float64], rate: float, t: float) -> float:
    i = int(t * rate)
    w = max(1, int(MATCH_S * rate))
    window = env[max(0, i - w) : i + w + 1]
    return float(window.max()) if len(window) else 0.0


def onset_at_beats(
    env: npt.NDArray[np.float64], rate: float, beats: list[float]
) -> tuple[float, float]:
    """(mean onset strength at the beats, mean at the midpoints between them)."""
    if len(beats) < 2:  # noqa: PLR2004
        return 0.0, 0.0
    at = [_peak_near(env, rate, t) for t in beats]
    mids = [_peak_near(env, rate, (a + b) / 2) for a, b in pairwise(beats)]
    return float(np.mean(at)), float(np.mean(mids))


def onset_peaks(env: npt.NDArray[np.float64], rate: float) -> list[float]:
    """Times of strong onsets (the energy-grid fallback cuts on these)."""
    from scipy.signal import find_peaks

    if len(env) == 0:
        return []
    height = float(env.mean() + env.std())
    idx, _ = find_peaks(env, height=height, distance=max(1, int(0.2 * rate)))
    return [float(i) / rate for i in idx]


def audio_condition(signal: FloatArray, sr: int) -> float:
    """S8: 1.0 for a normal recording; lower for a long lead-in, near silence or a low level."""
    if len(signal) == 0:
        return 0.0
    peak = float(np.abs(signal).max())
    if peak < 1e-4:  # noqa: PLR2004
        return 0.0
    score = 1.0
    lead = int(np.argmax(np.abs(signal) > 0.01 * peak)) / sr
    if lead > 3.0:  # noqa: PLR2004
        score -= 0.3
    db = np.asarray(rms_db(signal, sr))
    if len(db) and float((db < SILENT_DB).mean()) > 0.5:  # noqa: PLR2004
        score -= 0.4
    if peak < 0.05:  # noqa: PLR2004
        score -= 0.3
    return max(0.0, score)


# --- render verification (plan 007): cut positions and the Mode A offset --------------------------

XCORR_SR = 8000  # the audio is compared at 8 kHz mono: 0.125 ms per sample
XCORR_MAX_LAG_S = 0.2
Float64 = npt.NDArray[np.float64]


def frame_diffs(frames: npt.NDArray[np.uint8]) -> list[float]:
    """`d[f]` = mean absolute difference of gray frame f against f - 1 (`d[0]` is 0); `frames` is
    `(n, h, w)` or `(n, h * w)`. QUALITY §7 cut positions."""
    if len(frames) == 0:
        return []
    flat = frames.reshape(len(frames), -1).astype(np.int16)
    d = np.abs(np.diff(flat, axis=0)).mean(axis=1)
    return [0.0, *(float(v) for v in d)]


def _click_envelope(x: Float64, sr: int) -> Float64:
    """Rectify, 4 ms boxcar, half-wave rectified first difference (the spike's onset envelope)."""
    k = max(1, int(0.004 * sr))
    env = np.convolve(np.abs(x), np.ones(k) / k, mode="same")
    return np.asarray(np.maximum(np.diff(env, prepend=env[0]), 0.0), dtype=np.float64)


def _parabolic_peak(y: Float64, k: int) -> float:
    if k <= 0 or k >= len(y) - 1:
        return float(k)
    y0, y1, y2 = y[k - 1], y[k], y[k + 1]
    denom = y0 - 2 * y1 + y2
    return float(k) if denom == 0 else float(k + 0.5 * (y0 - y2) / denom)


def xcorr_offset(
    ref: Float64, test: Float64, sr: int = XCORR_SR, max_lag_s: float = XCORR_MAX_LAG_S
) -> float:
    """Offset in seconds of `test` against `ref` (positive: `test` is late): FFT cross-correlation
    of the onset envelopes with a parabolic refinement of the peak."""
    n = min(len(ref), len(test))
    a, b = _click_envelope(ref[:n], sr), _click_envelope(test[:n], sr)
    nfft = 1 << int(np.ceil(np.log2(2 * n)))
    c = np.fft.irfft(np.fft.rfft(b, nfft) * np.conj(np.fft.rfft(a, nfft)), nfft)
    c = np.concatenate([c[-(n - 1) :], c[:n]])  # lags -(n-1) .. n-1
    m = int(max_lag_s * sr)
    seg = c[n - 1 - m : n + m]
    k = int(np.argmax(seg))
    return (_parabolic_peak(seg, k) - m) / sr


def onset_offsets(
    ref: Float64, test: Float64, duration_s: float, sr: int = XCORR_SR
) -> tuple[float, float, float]:
    """`(offset at t~1 s, offset at t~end-1 s, drift per 60 s)` of `test` against `ref`, from the
    first and last 2 s (QM-067/068)."""
    w = int(2.0 * sr)
    n = min(len(ref), len(test))
    start = xcorr_offset(ref[:w], test[:w], sr)
    end = xcorr_offset(ref[n - w : n], test[n - w : n], sr)
    return start, end, (end - start) * (60.0 / max(duration_s - 2.0, 1.0))

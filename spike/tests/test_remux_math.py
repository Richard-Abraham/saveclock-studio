import numpy as np

from spike.remux import SR, find_run, xcorr_offset


def clicks(n_s: float, times: list[float]) -> np.ndarray:  # type: ignore[type-arg]
    x = np.zeros(int(n_s * SR))
    for t in times:
        i = int(t * SR)
        x[i : i + 80] = np.sin(np.arange(80) * 2 * np.pi * 1000 / SR)
    return x


def test_xcorr_recovers_known_offset() -> None:
    ts = [0.2 + 0.5 * k for k in range(8)]
    ref = clicks(4.5, ts)
    for off in (0.0, 0.0125, -0.021):
        got = clicks(4.5, [t + off for t in ts])
        assert abs(xcorr_offset(ref, got) - off) < 0.001


def test_find_run() -> None:
    assert find_run(list("abcdef"), list("cde")) == 2
    assert find_run(list("abcdef"), list("cdx")) is None
    assert find_run(list("abc"), []) is None

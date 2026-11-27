import json
from pathlib import Path

import pytest

from saveclock_eval.bench_summary import main, peak_rss_mb


def test_peak_rss_parse() -> None:
    assert peak_rss_mb("x\n\tMaximum resident set size (kbytes): 2048\n") == 2.0
    with pytest.raises(ValueError):
        peak_rss_mb("nothing")


def test_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    j = tmp_path / "r.json"
    t = tmp_path / "r.time"
    j.write_text(
        json.dumps({"run_s": [9.0] + [5.0] * 3 + [1.0] * 10, "model_load_s": 0.1, "n_beats": 3})
    )
    t.write_text("Maximum resident set size (kbytes): 1024\n")
    assert main([str(j), str(t)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["cold_s"] == 9.0 and out["mean_s"] == 1.0 and out["n_timed"] == 10
    assert out["peak_rss_mb"] == 1.0

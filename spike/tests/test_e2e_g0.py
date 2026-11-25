"""End-to-end harness run on the system ffmpeg; slow, skipped unless ``G0_E2E=1``."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(os.environ.get("G0_E2E") != "1", reason="slow e2e; set G0_E2E=1")
def test_one_case_end_to_end(tmp_path: Path) -> None:
    out = tmp_path / "r.json"
    cmd = [
        sys.executable, "-I", "-m", "spike.run_g0_render", "--ffmpeg", "/usr/bin/ffmpeg",
        "--out", str(out), "--only", "R00", "--no-bench", "--no-progress-test",
        "--work", str(Path.home() / "saveclock-spike/data/results/renders/e2e"),
    ]  # fmt: skip
    assert subprocess.run(cmd, shell=False, timeout=900, check=False).returncode == 0
    assert out.exists()

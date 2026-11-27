"""scripts/saveclock keeps the caller's directory and works through a symlink (plan 009, P9-18)."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
WRAPPER = ROOT / "scripts" / "saveclock"
pytestmark = pytest.mark.skipif(shutil.which("uv") is None, reason="needs uv")


def _run(argv: list[str], cwd: Path, wrapper: Path = WRAPPER) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "SAVECLOCK_API_URL"}
    return subprocess.run(  # noqa: S603
        [str(wrapper), *argv],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


@pytest.mark.unit
def test_help_runs_from_any_directory(tmp_path: Path) -> None:
    r = _run(["--help"], tmp_path)
    assert r.returncode == 0
    for command in ("new", "show", "keywords", "plan", "render", "export", "status", "open"):
        assert command in r.stdout


@pytest.mark.unit
def test_a_symlinked_install_works(tmp_path: Path) -> None:
    link = tmp_path / "saveclock"
    link.symlink_to(WRAPPER)
    r = _run(["--help"], tmp_path, link)
    assert r.returncode == 0, r.stderr


@pytest.mark.unit
def test_the_callers_directory_is_kept_not_the_projects(tmp_path: Path) -> None:
    # a relative export directory that exists only in the caller's directory must be accepted;
    # under `uv --directory services/api` it would be looked up there and refused
    (tmp_path / "out").mkdir()
    r = _run(
        [
            "--api-url",
            "http://127.0.0.1:9",
            "export",
            "00000000-0000-4000-8000-000000000000",
            "--mode",
            "b",
            "--out",
            "./out",
        ],
        tmp_path,
    )
    assert "output directory does not exist" not in r.stderr
    assert r.returncode == 3  # reached the network step (nothing listens on port 9), not usage


@pytest.mark.unit
def test_a_non_loopback_url_exits_2_with_a_refusal(tmp_path: Path) -> None:
    r = _run(["--api-url", "http://example.com", "status"], tmp_path)
    assert r.returncode == 2
    assert "refus" in r.stderr


@pytest.mark.unit
def test_the_wrapper_text_keeps_its_three_properties() -> None:
    text = WRAPPER.read_text()
    assert "--directory" not in text
    assert "--locked" in text
    assert 'readlink -f "$0"' in text

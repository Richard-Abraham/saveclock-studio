from pathlib import Path

import pytest

from saveclock.services.autotune import HostFacts, detect, effective, host_facts
from tests.unit.test_config import make_settings


@pytest.mark.unit
@pytest.mark.parametrize(
    ("cpu", "ram", "heavy"),
    [(4, 23, 1), (16, 32, 4), (16, 8, 2), (2, 3, 1), (8, 64, 2), (8, 4, 1)],
)
def test_detect_heavy_hand_computed(cpu: int, ram: float, heavy: int) -> None:
    t = detect(cpu, ram)
    assert t.heavy == heavy
    assert t.torch_threads == cpu
    assert t.ffmpeg_threads == cpu
    assert t.fetch_concurrency == 4
    assert t.device == "cpu"


@pytest.mark.unit
def test_override_wins_and_is_marked() -> None:
    t = effective(make_settings(FETCH_CONCURRENCY="7"), HostFacts(cpu=4, ram_gb=8))
    assert t.fetch_concurrency == 7
    assert t.source["fetch_concurrency"] == "override"
    assert t.source["heavy"] == "auto"


@pytest.mark.unit
def test_unset_override_stays_auto() -> None:
    t = effective(make_settings(), HostFacts(cpu=4, ram_gb=8))
    assert t.fetch_concurrency == 4
    assert t.source["fetch_concurrency"] == "auto"


@pytest.mark.unit
def test_host_facts_reads_cgroup(tmp_path: Path) -> None:
    (tmp_path / "cpu.max").write_text("300000 100000\n")
    (tmp_path / "memory.max").write_text(str(4 * 1024**3) + "\n")
    assert host_facts(tmp_path) == HostFacts(cpu=3, ram_gb=4.0)


@pytest.mark.unit
def test_host_facts_falls_back_when_unlimited(tmp_path: Path) -> None:
    (tmp_path / "cpu.max").write_text("max 100000\n")
    (tmp_path / "memory.max").write_text("max\n")
    facts = host_facts(tmp_path)
    assert facts.cpu >= 1
    assert facts.ram_gb > 0

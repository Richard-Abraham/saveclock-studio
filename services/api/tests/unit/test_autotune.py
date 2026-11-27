from pathlib import Path

import pytest

from saveclock.services.autotune import HostFacts, detect, effective, host_facts
from saveclock.services.tuning import get_tuning
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


@pytest.mark.unit
@pytest.mark.parametrize(
    ("cpu", "ram", "heavy"),
    [
        (2, 4, 1), (2, 8, 1), (2, 16, 1), (2, 32, 1),
        (4, 4, 1), (4, 8, 1), (4, 16, 1), (4, 32, 1),
        (8, 4, 1), (8, 8, 2), (8, 16, 2), (8, 32, 2),
        (16, 4, 1), (16, 8, 2), (16, 16, 4), (16, 32, 4),
    ],
)  # fmt: skip
def test_the_heavy_grid_is_hand_computed(cpu: int, ram: int, heavy: int) -> None:
    # DECISIONS §8g: heavy = max(1, min(cpu // 4, (ram_gb - 2) // 3)), literals worked by hand
    assert detect(cpu, ram).heavy == heavy


@pytest.mark.unit
def test_the_cgroup_ram_term_decides(tmp_path: Path) -> None:
    (tmp_path / "cpu.max").write_text("800000 100000\n")  # 8 CPUs
    (tmp_path / "memory.max").write_text(str(8 * 1024**3) + "\n")  # (8 - 2) // 3 = 2 < 8 // 4 + ...
    facts = host_facts(tmp_path)
    assert facts == HostFacts(cpu=8, ram_gb=8.0)
    assert detect(facts.cpu, facts.ram_gb).heavy == 2


@pytest.mark.unit
def test_max_in_either_cgroup_file_means_no_limit(tmp_path: Path) -> None:
    (tmp_path / "cpu.max").write_text("max 100000\n")
    (tmp_path / "memory.max").write_text(str(4 * 1024**3) + "\n")
    facts = host_facts(tmp_path)
    assert facts.ram_gb == 4.0
    assert facts.cpu >= 1


@pytest.mark.unit
def test_get_tuning_is_memoised_on_the_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    get_tuning.cache_clear()  # type: ignore[attr-defined]
    a = get_tuning(make_settings())
    assert get_tuning(make_settings()) is a
    b = get_tuning(make_settings(FETCH_CONCURRENCY="9"))
    assert b is not a
    assert b.fetch_concurrency == 9
    assert b.source["fetch_concurrency"] == "override"
    get_tuning.cache_clear()  # type: ignore[attr-defined]

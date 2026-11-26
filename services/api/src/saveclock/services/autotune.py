"""Self-tuning of worker concurrency (DECISIONS §8g)."""

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from saveclock.config import Settings

Source = Literal["auto", "override"]
CGROUP = Path("/sys/fs/cgroup")
GB = 1024**3


@dataclass(frozen=True)
class HostFacts:
    cpu: int
    ram_gb: float


@dataclass(frozen=True)
class Tuning:
    heavy: int
    torch_threads: int
    ffmpeg_threads: int
    fetch_concurrency: int
    device: str
    source: dict[str, Source]


def detect(cpu: int, ram_gb: float) -> Tuning:
    """DECISIONS §8g: heavy = max(1, min(cpu // 4, (ram_gb - 2) // 3))."""
    heavy = max(1, min(cpu // 4, int((ram_gb - 2) // 3)))
    auto: dict[str, Source] = dict.fromkeys(
        ("heavy", "torch_threads", "ffmpeg_threads", "fetch_concurrency", "device"), "auto"
    )
    return Tuning(
        heavy=heavy,
        torch_threads=cpu,
        ffmpeg_threads=cpu,
        fetch_concurrency=4,
        device="cpu",
        source=auto,
    )


def _cgroup_cpu(root: Path) -> int | None:
    try:
        quota, period = (root / "cpu.max").read_text().split()
    except (OSError, ValueError):
        return None
    if quota == "max":
        return None
    return max(1, int(int(quota) / int(period)))


def _cgroup_ram(root: Path) -> float | None:
    try:
        raw = (root / "memory.max").read_text().strip()
    except OSError:
        return None
    return None if raw == "max" else int(raw) / GB


def _meminfo_gb() -> float:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemTotal:"):
            return int(line.split()[1]) * 1024 / GB
    return 4.0  # shortcut: assume 4 GB without /proc/meminfo, upgrade if a non-Linux host appears


def host_facts(root: Path = CGROUP) -> HostFacts:
    cpu = _cgroup_cpu(root) or os.cpu_count() or 1
    ram = _cgroup_ram(root) or _meminfo_gb()
    return HostFacts(cpu=cpu, ram_gb=ram)


def effective(settings: Settings, facts: HostFacts) -> Tuning:
    """Auto values with the optional overrides from `Settings` applied (None = auto)."""
    t = detect(facts.cpu, facts.ram_gb)
    overrides: dict[str, int | str | None] = {
        "heavy": settings.worker_heavy_concurrency,
        "torch_threads": settings.torch_threads,
        "ffmpeg_threads": settings.ffmpeg_threads,
        "fetch_concurrency": settings.fetch_concurrency,
        "device": settings.device if settings.device != "cpu" else None,
    }
    chosen = {name: value for name, value in overrides.items() if value is not None}
    source: dict[str, Source] = {**t.source, **dict.fromkeys(chosen, "override")}
    return replace(t, **chosen, source=source)  # type: ignore[arg-type]

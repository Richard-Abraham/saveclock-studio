"""The one accessor for the effective tuning: every call site asks here, none reads the host."""

from functools import lru_cache

from saveclock.config import Settings
from saveclock.services.autotune import Tuning, effective, host_facts


@lru_cache(maxsize=16)
def _tuning(
    heavy: int | None,
    torch_threads: int | None,
    ffmpeg_threads: int | None,
    fetch_concurrency: int | None,
    device: str,
) -> Tuning:
    probe = Settings.model_construct(
        worker_heavy_concurrency=heavy,
        torch_threads=torch_threads,
        ffmpeg_threads=ffmpeg_threads,
        fetch_concurrency=fetch_concurrency,
        device=device,
    )
    return effective(probe, host_facts())


def get_tuning(settings: Settings) -> Tuning:
    """`effective(settings, host_facts())` memoised per process on the five override fields."""
    return _tuning(
        settings.worker_heavy_concurrency,
        settings.torch_threads,
        settings.ffmpeg_threads,
        settings.fetch_concurrency,
        settings.device,
    )


get_tuning.cache_clear = _tuning.cache_clear  # type: ignore[attr-defined]

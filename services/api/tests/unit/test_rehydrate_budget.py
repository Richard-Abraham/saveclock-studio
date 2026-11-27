"""Rehydration spends one budget: each clip's slot wait is what is left of it, never more."""

from types import SimpleNamespace
from typing import Any

import pytest

from saveclock.adapters.heavy_lock import HeavyLockTimeout
from saveclock.config import FOOTAGE_WAIT_S
from saveclock.errors import StockUnavailable
from saveclock.services import rehydrate


class _NoBlobs:
    def exists(self, key: str) -> bool:
        return (
            key.startswith("work/") and "/raw/" in key
        )  # the raw file is there, the mezzanine not


class _Session:
    async def __aenter__(self) -> "_Session":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


class _Emitter:
    async def aemit(self, *_: object, **__: object) -> None:
        return None


class _Candidates:
    def __init__(self, _session: object) -> None: ...

    async def get_by_provider_id(self, **_: object) -> None:
        return None


def _run(monkeypatch: pytest.MonkeyPatch, normalize: Any, deadline_s: float) -> Any:
    async def bookkeep(*_: object, **__: object) -> None:
        return None

    monkeypatch.setattr(rehydrate, "normalize_one", normalize)
    monkeypatch.setattr(rehydrate, "_bookkeep", bookkeep)
    monkeypatch.setattr(rehydrate, "CandidateRepository", _Candidates)
    monkeypatch.setattr(rehydrate, "raw_key", lambda *_: "work/p/raw/x.mp4")
    clip = SimpleNamespace(mezzanine_key="work/p/mezz/x.mp4", provider="pexels", provider_id="1")
    plan = SimpleNamespace(cuts=[SimpleNamespace(index=0, clip=clip)], version=1)
    deps = SimpleNamespace(
        ctx=SimpleNamespace(blobs=_NoBlobs(), sessionmaker=_Session), providers=[], cancel=None
    )
    return rehydrate.rehydrate_plan(
        deps,  # type: ignore[arg-type]
        plan,  # type: ignore[arg-type]
        user_id=None,  # type: ignore[arg-type]
        project_id=None,  # type: ignore[arg-type]
        emitter=_Emitter(),  # type: ignore[arg-type]
        deadline_s=deadline_s,
    )


@pytest.mark.unit
async def test_the_slot_wait_is_the_remaining_budget_capped_by_the_footage_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits: list[float] = []

    async def normalize(*_: object, wait_s: float, **__: object) -> Any:
        waits.append(wait_s)
        return SimpleNamespace(mezz_frames=None)

    await _run(monkeypatch, normalize, deadline_s=10)
    await _run(monkeypatch, normalize, deadline_s=10_000)
    assert 0 < waits[0] <= 10  # the budget, not FOOTAGE_WAIT_S
    assert waits[1] == FOOTAGE_WAIT_S  # a roomy budget keeps the usual wait


@pytest.mark.unit
async def test_a_slot_wait_that_spends_the_budget_is_the_retryable_stock_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def normalize(*_: object, **__: object) -> Any:
        raise HeavyLockTimeout

    with pytest.raises(StockUnavailable) as exc:
        await _run(monkeypatch, normalize, deadline_s=10)
    assert exc.value.details == {"reason": "rehydrate_deadline"}

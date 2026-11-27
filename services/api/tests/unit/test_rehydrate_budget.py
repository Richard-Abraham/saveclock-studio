"""Rehydration spends one budget: each clip's slot wait is what is left of it, never more."""

from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from saveclock.adapters.heavy_lock import HeavyLockTimeout
from saveclock.config import FOOTAGE_WAIT_S
from saveclock.errors import ClipUnavailable, StockUnavailable
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


@pytest.mark.unit
async def test_nothing_missing_rebuilds_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def normalize(*_: object, **__: object) -> Any:
        raise AssertionError("nothing to rebuild")

    monkeypatch.setattr(_NoBlobs, "exists", lambda _self, _key: True)
    assert await _run(monkeypatch, normalize, deadline_s=10) == 0


@pytest.mark.unit
async def test_a_spent_budget_stops_before_the_first_clip(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []

    async def normalize(*_: object, **__: object) -> Any:
        calls.append(1)
        return SimpleNamespace(mezz_frames=None)

    with pytest.raises(StockUnavailable) as exc:
        await _run(monkeypatch, normalize, deadline_s=0)
    assert exc.value.details == {"reason": "rehydrate_deadline"}
    assert calls == []


@pytest.mark.unit
async def test_a_rebuilt_clip_of_another_length_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def normalize(*_: object, **__: object) -> Any:
        return SimpleNamespace(mezz_frames=123)  # the stored candidate has no frame count

    with pytest.raises(ClipUnavailable) as exc:
        await _run(monkeypatch, normalize, deadline_s=10)
    assert exc.value.details == {"cut": 0}


class _Projects:
    updated: ClassVar[list[dict[str, object]]] = []

    def __init__(self, _session: object) -> None: ...

    async def get(self, **_: object) -> Any:
        return SimpleNamespace(flags={rehydrate.FLAG: {"version": 1, "cuts": [0]}, "other": 1})

    async def update_fields(self, *, values: dict[str, object], **_: object) -> None:
        self.updated.append(values)


class _CommitSession(_Session):
    async def commit(self) -> None:
        return None


@pytest.mark.unit
async def test_a_clean_rehydration_clears_an_old_unavailable_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rehydrate, "ProjectRepository", _Projects)
    deps = SimpleNamespace(ctx=SimpleNamespace(sessionmaker=_CommitSession))
    plan = SimpleNamespace(cuts=[], version=2)
    await rehydrate._bookkeep(
        deps,  # type: ignore[arg-type]
        plan,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        rebuilt=0,
        gone=[],
    )
    assert _Projects.updated == [{"flags": {"other": 1}}]

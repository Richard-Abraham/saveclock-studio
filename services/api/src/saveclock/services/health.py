"""Readiness: each dependency check is bounded and never leaks its error text."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping

Check = Callable[[], Awaitable[None]]
CHECK_TIMEOUT_S = 2.0


async def _run(check: Check) -> str:
    try:
        await asyncio.wait_for(check(), CHECK_TIMEOUT_S)
    except Exception:
        return "error"
    return "ok"


async def readiness(checks: Mapping[str, Check]) -> dict[str, str]:
    names = list(checks)
    results = await asyncio.gather(*(_run(checks[n]) for n in names))
    return dict(zip(names, results, strict=True))

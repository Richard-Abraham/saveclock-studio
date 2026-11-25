"""Read-only settings view (#24). The api never holds provider keys: it only sees the flags."""

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from typing import Any

from redis.asyncio import Redis

from saveclock.adapters.blobstore.port import BlobStore
from saveclock.config import Settings
from saveclock.services.identity import CurrentUser

TUNING_KEY = "settings:tuning"
USAGE_TTL_S = 60.0
AREAS = ("songs", "work", "renders")


@dataclass
class UsageCache:
    # shortcut: per-process cache, fine for one API process; use Redis if the api scales out.
    ttl: float = USAGE_TTL_S
    _values: dict[str, tuple[float, int]] = field(default_factory=dict)

    def get(self, key: str, load: Callable[[], int], now: float | None = None) -> int:
        now = time.monotonic() if now is None else now
        hit = self._values.get(key)
        if hit is not None and now - hit[0] < self.ttl:
            return hit[1]
        value = load()
        self._values[key] = (now, value)
        return value


def _usage_by_area(blobs: BlobStore, cache: UsageCache) -> dict[str, int]:
    return {area: cache.get(area, partial(blobs.usage, area)) for area in AREAS}


async def settings_view(
    settings: Settings, user: CurrentUser, redis: Redis, blobs: BlobStore, cache: UsageCache
) -> dict[str, Any]:
    stock = user.settings.get("stock", {})
    pixabay_enabled = bool(stock.get("pixabay_enabled", settings.pixabay_enabled))
    llm_enabled = settings.llm_enabled
    if llm_enabled is None:  # auto: on only when a key is configured
        llm_enabled = settings.anthropic_key_configured
    raw = await redis.get(TUNING_KEY)
    total, free = await asyncio.to_thread(blobs.volume)
    by_area = await asyncio.to_thread(_usage_by_area, blobs, cache)
    return {
        "keys": {
            "pexels": {"configured": settings.pexels_key_configured},
            "pixabay": {"configured": settings.pixabay_key_configured},
            "anthropic": {
                "configured": settings.anthropic_key_configured,
                "llm_enabled": llm_enabled,
                "fallback_active": not llm_enabled,
            },
        },
        "stock": {"pixabay_enabled": pixabay_enabled},
        "tuning": json.loads(raw) if raw else None,
        "disk": {"volume": {"total": total, "free": free}, "by_area": by_area, "projects": []},
    }

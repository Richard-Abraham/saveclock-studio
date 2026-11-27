"""The settings view (#24) and its one writer (#25). The api never holds provider keys: it only
sees the flags."""

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.adapters.blobstore.port import BlobStore
from saveclock.config import Settings
from saveclock.errors import NotFound, PixabayNotConfigured
from saveclock.repositories.projects import ProjectRepository
from saveclock.repositories.renders import RenderRepository
from saveclock.repositories.users import UserRepository
from saveclock.services.autotune import GB
from saveclock.services.identity import CurrentUser

TUNING_KEY = "settings:tuning"
USAGE_TTL_S = 60.0
AREAS = ("songs", "work", "renders")
MAX_PROJECT_ROWS = 100


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


@dataclass(frozen=True)
class ProjectBytes:
    """`bytes` is what is kept for good (the song and every render); `intermediate_bytes` is
    `work/{pid}`, which the sweeper removes."""

    project_id: UUID
    bytes: int
    intermediate_bytes: int

    @property
    def total(self) -> int:
        return self.bytes + self.intermediate_bytes


def _project_bytes(
    blobs: BlobStore, cache: UsageCache, project_id: UUID, render_ids: list[UUID]
) -> ProjectBytes:
    def keepers() -> int:
        return blobs.usage(f"songs/{project_id}") + sum(
            blobs.usage(f"renders/{rid}") for rid in render_ids
        )

    return ProjectBytes(
        project_id,
        cache.get(f"project:{project_id}", keepers),
        cache.get(f"project:{project_id}:work", partial(blobs.usage, f"work/{project_id}")),
    )


async def project_disk(
    session: AsyncSession,
    user_id: UUID,
    blobs: BlobStore,
    cache: UsageCache,
    project_ids: list[UUID],
) -> dict[UUID, ProjectBytes]:
    """Disk numbers per project (60 s cache); one query for every render id of the user."""
    by_project = await RenderRepository(session).ids_by_project(user_id=user_id)

    def load() -> dict[UUID, ProjectBytes]:
        return {
            pid: _project_bytes(blobs, cache, pid, by_project.get(pid, [])) for pid in project_ids
        }

    return await asyncio.to_thread(load)


async def settings_view(
    settings: Settings,
    user: CurrentUser,
    redis: Redis,
    blobs: BlobStore,
    cache: UsageCache,
    *,
    session: AsyncSession,
) -> dict[str, Any]:
    stock = user.settings.get("stock", {})
    pixabay_enabled = bool(stock.get("pixabay_enabled", settings.pixabay_enabled))
    llm_enabled = settings.llm_enabled
    if llm_enabled is None:  # auto: on only when a key is configured
        llm_enabled = settings.anthropic_key_configured
    raw = await redis.get(TUNING_KEY)
    total, free = await asyncio.to_thread(blobs.volume)
    by_area = await asyncio.to_thread(_usage_by_area, blobs, cache)
    rows = await ProjectRepository(session).list_all(user_id=user.id)
    disk = await project_disk(session, user.id, blobs, cache, [p.id for p in rows])
    ranked = sorted(rows, key=lambda p: (-disk[p.id].total, str(p.id)))[:MAX_PROJECT_ROWS]
    projects = [
        {
            "id": p.id,
            "title": p.title,
            "bytes": disk[p.id].bytes,
            "intermediate_bytes": disk[p.id].intermediate_bytes,
            "last_activity_at": p.last_activity_at,
        }
        for p in ranked
    ]
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
        "disk": {
            "volume": {"total": total, "free": free},
            "by_area": by_area,
            "projects": projects,
            "low": free < int(settings.disk_low_watermark_gb * GB),
        },
        "intermediate_ttl_days": settings.intermediate_ttl_days,
    }


async def put_settings(
    session: AsyncSession, settings: Settings, user: CurrentUser, *, pixabay_enabled: bool
) -> CurrentUser:
    """Store the Pixabay switch (§8d: `PUT /settings`). Enabling needs a configured key: the api
    only knows the flag the worker's key sets. Returns the user with the new settings."""
    if pixabay_enabled and not settings.pixabay_key_configured:
        raise PixabayNotConfigured
    merged = await UserRepository(session).update_settings(
        user_id=user.id, patch={"stock": {"pixabay_enabled": pixabay_enabled}}
    )
    if merged is None:
        raise NotFound
    await session.commit()
    return CurrentUser(id=user.id, display_name=user.display_name, settings=merged)

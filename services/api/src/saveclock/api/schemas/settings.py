from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Configured(_Model):
    configured: bool


class AnthropicKey(_Model):
    configured: bool
    llm_enabled: bool
    fallback_active: bool


class Keys(_Model):
    pexels: Configured
    pixabay: Configured
    anthropic: AnthropicKey


class Stock(_Model):
    pixabay_enabled: bool


class Tuning(_Model):
    heavy: int
    torch_threads: int
    ffmpeg_threads: int
    fetch_concurrency: int
    device: str
    source: dict[str, Literal["auto", "override"]]


class Volume(_Model):
    total: int
    free: int


class ByArea(_Model):
    songs: int
    work: int
    renders: int


class ProjectDisk(_Model):
    id: UUID
    title: str | None
    bytes: int  # kept until the owner deletes the project: the song and every render
    intermediate_bytes: int  # work/{id}: swept after the retention period, rebuilt on demand
    last_activity_at: datetime


class Disk(_Model):
    volume: Volume
    by_area: ByArea
    projects: list[ProjectDisk]  # at most 100, biggest first
    low: bool  # free space is under DISK_LOW_WATERMARK_GB


class SettingsOut(_Model):
    keys: Keys
    stock: Stock
    tuning: Tuning | None
    disk: Disk
    intermediate_ttl_days: int


class SettingsPut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pixabay_enabled: bool

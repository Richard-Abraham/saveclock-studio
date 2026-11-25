from typing import Literal

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


class Disk(_Model):
    volume: Volume
    by_area: ByArea
    projects: list[str]  # per-project rows arrive in Phase 2/4; always empty now


class SettingsOut(_Model):
    keys: Keys
    stock: Stock
    tuning: Tuning | None
    disk: Disk

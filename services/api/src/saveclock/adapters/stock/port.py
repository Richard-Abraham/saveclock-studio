"""The stock provider port, and the one place the provider hosts are spelled out (P5-5)."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from saveclock.adapters.blobstore.port import BlobStore

# Download and API hosts (SEC-019). `STOCK_HOST_ALLOWLIST` may only ADD to these.
PEXELS_HOSTS = frozenset({"api.pexels.com", "videos.pexels.com", "images.pexels.com"})
PIXABAY_HOSTS = frozenset({"pixabay.com", "cdn.pixabay.com"})
PREFERRED_WIDTH = 1080  # the closest file at or above this width wins
MIN_WIDTH = 720


@dataclass(frozen=True)
class StockClip:
    provider: str
    provider_id: str
    page_url: str
    author: str | None
    author_url: str | None
    license: str
    width: int
    height: int
    duration_s: float
    fps: float | None
    file_url: str
    file_size: int | None = None


class StockProvider(Protocol):
    name: str

    def search(self, query: str, *, page: int = 1, per_page: int = 40) -> list[StockClip]: ...

    def download(
        self,
        clip: StockClip,
        blobs: BlobStore,
        key: str,
        *,
        max_bytes: int,
        cancel: Callable[[], bool] | None,
    ) -> int: ...


def pick_file_width(widths: list[int]) -> int | None:
    """The index of the best file: closest to but not below 1080 wide, else the largest >= 720."""
    eligible = [(w, i) for i, w in enumerate(widths) if w >= MIN_WIDTH]
    if not eligible:
        return None
    above = [(w, i) for w, i in eligible if w >= PREFERRED_WIDTH]
    return min(above)[1] if above else max(eligible)[1]

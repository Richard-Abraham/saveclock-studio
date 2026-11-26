"""Which hosts a clip may be fetched from, and the download call every provider shares."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

import httpx

from saveclock.adapters.blobstore.port import BlobStore
from saveclock.adapters.safe_http import Resolver, resolve_all, safe_download
from saveclock.adapters.stock.port import PEXELS_HOSTS, PIXABAY_HOSTS, StockClip


def allowed_hosts(extra: Iterable[str] = (), *, pixabay: bool = False) -> frozenset[str]:
    """The Pexels hosts (a code constant), plus `STOCK_HOST_ALLOWLIST` entries, plus the Pixabay
    hosts only while that provider is switched on (P5-5)."""
    hosts = set(PEXELS_HOSTS) | {h.strip().lower() for h in extra if h.strip()}
    if pixabay:
        hosts |= PIXABAY_HOSTS
    return frozenset(hosts)


@dataclass(frozen=True)
class Downloader:
    hosts: frozenset[str] = field(default_factory=allowed_hosts)
    resolver: Resolver = resolve_all
    client: httpx.Client | None = None

    def fetch(
        self,
        clip: StockClip,
        blobs: BlobStore,
        key: str,
        *,
        max_bytes: int,
        cancel: Callable[[], bool] | None,
    ) -> int:
        return safe_download(
            clip.file_url,
            blobs,
            key,
            hosts=self.hosts,
            max_bytes=max_bytes,
            resolver=self.resolver,
            cancel=cancel,
            client=self.client,
        )

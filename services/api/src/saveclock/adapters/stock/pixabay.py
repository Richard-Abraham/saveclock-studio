"""Pixabay video search (API docs: https://pixabay.com/api/docs/, the video section).

Pixabay passes the key as a query-string parameter, so the URL is built here and never logged
(P5-11). Queried only while the effective switch is on and a key exists (the service decides).
Pixabay has no orientation filter, so portrait renditions are picked locally.
"""

from collections.abc import Callable
from typing import Any

from saveclock.adapters.blobstore.port import BlobStore
from saveclock.adapters.stock.download import Downloader
from saveclock.adapters.stock.limits import ProviderHttp, SearchCache
from saveclock.adapters.stock.port import StockClip, pick_file_width
from saveclock.errors import StockUnavailable

SEARCH_URL = "https://pixabay.com/api/videos/"
LICENSE = "Pixabay Content License"
RENDITIONS = ("large", "medium", "small", "tiny")


def parse_hits(data: dict[str, Any]) -> list[StockClip]:
    clips: list[StockClip] = []
    for hit in data.get("hits", []):
        files = [
            r
            for name in RENDITIONS
            if (r := (hit.get("videos") or {}).get(name))
            and r.get("url")
            and int(r.get("width", 0)) < int(r.get("height", 0))
        ]
        best = pick_file_width([int(r["width"]) for r in files])
        if best is None:
            continue
        r, user = files[best], str(hit.get("user", ""))
        user_id = hit.get("user_id")
        clips.append(
            StockClip(
                provider="pixabay",
                provider_id=str(hit["id"]),
                page_url=str(hit.get("pageURL", "")),
                author=user or None,
                author_url=f"https://pixabay.com/users/{user}-{user_id}/" if user_id else None,
                license=LICENSE,
                width=int(r["width"]),
                height=int(r["height"]),
                duration_s=float(hit.get("duration", 0)),
                fps=None,
                file_url=str(r["url"]),
                file_size=int(r["size"]) if r.get("size") else None,
            )
        )
    return clips


class PixabayProvider:
    name = "pixabay"

    def __init__(
        self,
        http: ProviderHttp,
        key: str,
        cache: SearchCache,
        downloader: Downloader | None = None,
    ) -> None:
        self._http, self._key, self._cache = http, key, cache
        self._downloader = downloader or Downloader()

    def search(self, query: str, *, page: int = 1, per_page: int = 40) -> list[StockClip]:
        params: dict[str, Any] = {"q": query, "per_page": per_page, "page": page}
        cached = self._cache.get(params)  # the key is not part of the cache key
        if cached is not None:
            return cached
        data = self._http.get_json(SEARCH_URL, params={**params, "key": self._key})
        try:
            clips = parse_hits(data)
        except (KeyError, TypeError, ValueError, AttributeError):
            raise StockUnavailable(
                "stock provider sent a malformed answer", {"reason": "bad_body"}
            ) from None
        self._cache.set(params, clips)
        return clips

    def download(
        self,
        clip: StockClip,
        blobs: BlobStore,
        key: str,
        *,
        max_bytes: int,
        cancel: Callable[[], bool] | None,
    ) -> int:
        return self._downloader.fetch(clip, blobs, key, max_bytes=max_bytes, cancel=cancel)

"""Pexels video search (API docs: https://www.pexels.com/api/documentation/#videos-search).

The key goes only in the `Authorization` header. Nothing here logs a URL.
"""

from collections.abc import Callable
from typing import Any

from saveclock.adapters.blobstore.port import BlobStore
from saveclock.adapters.stock.download import Downloader
from saveclock.adapters.stock.limits import ProviderHttp, SearchCache
from saveclock.adapters.stock.port import StockClip, pick_file_width
from saveclock.errors import StockUnavailable

SEARCH_URL = "https://api.pexels.com/videos/search"
VIDEO_URL = "https://api.pexels.com/videos/videos/"  # + id (rehydration, plan 008)
LICENSE = "Pexels License"
# The documented `size` is a MINIMUM: large = 4K, medium = Full HD, small = HD. The plan said
# `large`, which would keep only 4K clips; `medium` matches the "closest to 1080" rule below.
# hypothesis: revisit with a real key (G0-17) by counting results per size.
SEARCH_SIZE = "medium"
MP4 = "video/mp4"


def parse_videos(data: dict[str, Any]) -> list[StockClip]:
    """The portrait mp4 file closest to (not below) 1080 wide per video, else the largest >= 720;
    videos without such a file, and landscape videos, are skipped."""
    clips: list[StockClip] = []
    for video in data.get("videos", []):
        if int(video.get("width", 0)) >= int(video.get("height", 0)):
            continue
        files = [
            f
            for f in video.get("video_files", [])
            if f.get("file_type") == MP4 and int(f.get("width", 0)) < int(f.get("height", 0))
        ]
        best = pick_file_width([int(f["width"]) for f in files])
        if best is None:
            continue
        f, user = files[best], video.get("user") or {}
        fps = f.get("fps")
        clips.append(
            StockClip(
                provider="pexels",
                provider_id=str(video["id"]),
                page_url=str(video.get("url", "")),
                author=user.get("name"),
                author_url=user.get("url"),
                license=LICENSE,
                width=int(f["width"]),
                height=int(f["height"]),
                duration_s=float(video.get("duration", 0)),
                fps=float(fps) if fps is not None else None,
                file_url=str(f["link"]),
            )
        )
    return clips


class PexelsProvider:
    name = "pexels"

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
        params = {
            "query": query,
            "orientation": "portrait",
            "size": SEARCH_SIZE,
            "per_page": per_page,
            "page": page,
        }
        cached = self._cache.get(params)
        if cached is not None:
            return cached
        data = self._http.get_json(SEARCH_URL, params=params, headers={"Authorization": self._key})
        try:
            clips = parse_videos(data)
        except (KeyError, TypeError, ValueError, AttributeError):
            raise StockUnavailable(
                "stock provider sent a malformed answer", {"reason": "bad_body"}
            ) from None
        self._cache.set(params, clips)
        return clips

    def video_by_id(self, provider_id: str) -> StockClip | None:
        """`GET /videos/videos/{id}`; a 404 or a clip with no usable file is None (gone)."""
        data = self._http.get_json(
            f"{VIDEO_URL}{provider_id}",
            params={},
            headers={"Authorization": self._key},
            not_found_ok=True,
        )
        try:
            clips = parse_videos({"videos": [data]}) if data else []
        except (KeyError, TypeError, ValueError, AttributeError):
            raise StockUnavailable(
                "stock provider sent a malformed answer", {"reason": "bad_body"}
            ) from None
        return clips[0] if clips and clips[0].provider_id == provider_id else None

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

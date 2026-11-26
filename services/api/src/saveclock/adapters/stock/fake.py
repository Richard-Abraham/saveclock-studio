"""FAKE_STOCK: serves the generated clips of `make fake-stock` (local and CI only)."""

import hashlib
import json
from collections.abc import Callable, Iterator
from pathlib import Path

from saveclock.adapters.blobstore.port import BlobStore
from saveclock.adapters.stock.port import StockClip

INDEX = "index.json"
CHUNK = 64 * 1024
FILE_URL = "fake://"


class FakeStockProvider:
    name = "pexels"  # rows use a real provider value: the table's CHECK allows only those

    def __init__(self, directory: str | Path) -> None:
        self.dir = Path(directory)
        try:
            index = json.loads((self.dir / INDEX).read_text())
        except (OSError, ValueError) as exc:
            msg = f"FAKE_STOCK_DIR {self.dir} has no readable {INDEX}: run `make fake-stock`"
            raise FileNotFoundError(msg) from exc
        self._clips = [
            StockClip(
                provider="pexels",
                provider_id=f"fake-{item['name']}",
                page_url=f"https://www.pexels.com/video/fake-{item['name']}/",
                author="Fake Author",
                author_url="https://www.pexels.com/@fake",
                license="Pexels License",
                width=item["width"],
                height=item["height"],
                duration_s=item["duration_s"],
                fps=item["fps"],
                file_url=f"{FILE_URL}{item['name']}.mp4",
            )
            for item in index["clips"]
        ]

    def search(self, query: str, *, page: int = 1, per_page: int = 40) -> list[StockClip]:
        """Every clip on page 1, rotated by a hash of the query (keywords give different orders)."""
        if page != 1:
            return []
        shift = int(hashlib.sha256(query.encode()).hexdigest(), 16) % len(self._clips)
        return (self._clips[shift:] + self._clips[:shift])[:per_page]

    def download(
        self,
        clip: StockClip,
        blobs: BlobStore,
        key: str,
        *,
        max_bytes: int,
        cancel: Callable[[], bool] | None,
    ) -> int:
        name = clip.file_url.removeprefix(FILE_URL)
        known = {c.file_url.removeprefix(FILE_URL) for c in self._clips}
        if name not in known:  # never a path the index did not list
            raise FileNotFoundError(name)
        return blobs.put(key, _read(self.dir / name, cancel), max_bytes=max_bytes)


def _read(path: Path, cancel: Callable[[], bool] | None) -> Iterator[bytes]:
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            if cancel is not None and cancel():
                msg = "canceled"
                raise InterruptedError(msg)
            yield chunk

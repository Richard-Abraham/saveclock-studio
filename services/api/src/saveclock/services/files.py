"""Serving blobs to the owner's browser (ARCH §9): allowlisted keys only, ranges supported."""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from http import HTTPStatus
from urllib.parse import quote

from saveclock.adapters.blobstore.blob_keys import is_servable
from saveclock.adapters.blobstore.port import BlobStore
from saveclock.errors import NotFound, RangeNotSatisfiable

CONTENT_TYPES = {
    ".txt": "text/plain; charset=utf-8",
    ".mp4": "video/mp4",
    ".json": "application/json",
    ".csv": "text/csv; charset=utf-8",
    ".m4a": "audio/mp4",
}
_RANGE = re.compile(r"bytes=(\d*)-(\d*)")


@dataclass(frozen=True)
class Served:
    status: int
    headers: dict[str, str]
    body: Iterator[bytes] = field(repr=False)


def _parse_range(header: str, size: int) -> tuple[int, int]:
    """One `bytes=a-b`, `bytes=a-` or `bytes=-n` range -> inclusive (start, end)."""
    m = _RANGE.fullmatch(header.strip())
    if m is None or (m.group(1) == "" and m.group(2) == ""):
        raise RangeNotSatisfiable(size)
    first, last = m.group(1), m.group(2)
    if first == "":  # suffix: the final n bytes
        n = int(last)
        if n == 0:
            raise RangeNotSatisfiable(size)
        return max(size - n, 0), size - 1
    start = int(first)
    end = min(int(last), size - 1) if last else size - 1
    if start >= size or end < start:
        raise RangeNotSatisfiable(size)
    return start, end


_ASCII_KEEP = re.compile(r"[^A-Za-z0-9._-]")


def attachment(name: str) -> str:
    """RFC 6266: an ASCII fallback (`[A-Za-z0-9._-]` only, so no quote or CR/LF can get in) and
    `filename*` with the full name percent-encoded."""
    fallback = _ASCII_KEEP.sub("", name) or "download"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(name, safe='')}"


def serve(
    blobs: BlobStore, key: str, range_header: str | None, *, download_name: str | None = None
) -> Served:
    # 404, not 403: a key we do not serve must not reveal whether it exists.
    if not is_servable(key):
        raise NotFound
    size = blobs.stat(key).size
    name = key.rsplit("/", 1)[-1]
    ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    headers = {
        "content-type": CONTENT_TYPES.get(ext, "application/octet-stream"),
        "content-disposition": attachment(download_name)
        if download_name is not None
        else f'attachment; filename="{name}"',
        "accept-ranges": "bytes",
    }
    if range_header is None:
        headers["content-length"] = str(size)
        return Served(HTTPStatus.OK, headers, blobs.open(key))
    start, end = _parse_range(range_header, size)
    headers["content-range"] = f"bytes {start}-{end}/{size}"
    headers["content-length"] = str(end - start + 1)
    return Served(HTTPStatus.PARTIAL_CONTENT, headers, blobs.open(key, (start, end)))

"""The BlobStore port (ARCH §9): FilesystemBlobStore now, S3BlobStore (stub) in Phase P."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class BlobStat:
    size: int
    mtime: float  # seconds since the epoch


class BlobStore(Protocol):
    def put(self, key: str, stream: Iterable[bytes], *, max_bytes: int) -> int: ...

    def open(self, key: str, range: tuple[int, int] | None = None) -> Iterator[bytes]: ...

    def stat(self, key: str) -> BlobStat: ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None: ...

    def rename(self, src_key: str, dst_key: str) -> None:
        """Atomic move within the store; NotFound if the source is missing."""
        ...

    def delete_prefix(self, prefix: str) -> int: ...

    def list(self, prefix: str) -> list[str]: ...

    def usage(self, prefix: str = "") -> int: ...

    def local_path(self, key: str) -> Path: ...

    def ensure_free_space(self, needed: int) -> None: ...

    def volume(self) -> tuple[int, int]:
        """(total, free) bytes of the volume."""
        ...

    def probe(self) -> None:
        """Raise unless the store is writable and above the free-space watermark (readiness)."""
        ...

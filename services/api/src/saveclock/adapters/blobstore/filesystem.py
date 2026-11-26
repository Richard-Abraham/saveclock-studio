"""FilesystemBlobStore: keys map to files under one root, nothing escapes it (SEC-160)."""

import contextlib
import os
import shutil
import stat as statmod
import uuid
from collections.abc import Iterable, Iterator
from pathlib import Path

from saveclock.adapters.blobstore.blob_keys import InvalidKey, validate_key
from saveclock.adapters.blobstore.port import BlobStat
from saveclock.errors import InsufficientStorage, NotFound, PayloadTooLarge

CHUNK = 64 * 1024
GB = 1024**3
PROBE_NAME = ".ready-probe"


class FilesystemBlobStore:
    # shortcut: path checks and the later open are not atomic (TOCTOU); the final open uses
    # O_NOFOLLOW and only our own processes write the volume, upgrade to openat2 if that changes.
    def __init__(self, root: str | Path, low_watermark_gb: float = 5) -> None:
        self.root = Path(os.path.realpath(root))
        self.low_watermark = int(low_watermark_gb * GB)

    def _resolve(self, key: str, *, allow_empty: bool = False) -> Path:
        """Validate the key, refuse symlinks on every existing component, stay under the root."""
        validate_key(key, allow_empty=allow_empty)
        current = self.root
        for segment in [s for s in key.split("/") if s]:
            current = current / segment
            try:
                mode = os.lstat(current).st_mode
            except FileNotFoundError:
                continue
            if statmod.S_ISLNK(mode):
                msg = "symlinks are not allowed"
                raise InvalidKey(msg)
        if not Path(os.path.realpath(current)).is_relative_to(self.root):
            msg = "key escapes the blob root"
            raise InvalidKey(msg)
        return current

    def _mkdirs(self, directory: Path) -> None:
        missing = []
        while directory != self.root and not directory.exists():
            missing.append(directory)
            directory = directory.parent
        for d in reversed(missing):
            d.mkdir(mode=0o700, exist_ok=True)
            d.chmod(0o700)

    def put(self, key: str, stream: Iterable[bytes], *, max_bytes: int) -> int:
        path = self._resolve(key)
        self._mkdirs(path.parent)
        part = path.with_name(path.name + ".part")
        fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        written = 0
        try:
            with os.fdopen(fd, "wb") as out:
                for chunk in stream:
                    if written + len(chunk) > max_bytes:
                        raise PayloadTooLarge("upload exceeds the size limit")
                    out.write(chunk)
                    written += len(chunk)
                out.flush()
                os.fsync(out.fileno())
            os.replace(part, path)
        except BaseException:
            part.unlink(missing_ok=True)
            raise
        return written

    def stat(self, key: str) -> BlobStat:
        path = self._resolve(key)
        try:
            st = os.lstat(path)
        except FileNotFoundError:
            raise NotFound from None
        if not statmod.S_ISREG(st.st_mode):
            raise NotFound
        return BlobStat(size=st.st_size)

    def exists(self, key: str) -> bool:
        try:
            self.stat(key)
        except NotFound:
            return False
        return True

    def open(self, key: str, range: tuple[int, int] | None = None) -> Iterator[bytes]:
        """Inclusive byte range. Key and symlink checks happen now, reading happens lazily."""
        path = self._resolve(key)
        self.stat(key)
        return self._read(path, range)

    @staticmethod
    def _read(path: Path, range_: tuple[int, int] | None) -> Iterator[bytes]:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as f:
            remaining = None
            if range_ is not None:
                f.seek(range_[0])
                remaining = range_[1] - range_[0] + 1
            while remaining is None or remaining > 0:
                data = f.read(CHUNK if remaining is None else min(CHUNK, remaining))
                if not data:
                    return
                if remaining is not None:
                    remaining -= len(data)
                yield data

    def delete(self, key: str) -> None:
        self._resolve(key).unlink(missing_ok=True)

    def delete_prefix(self, prefix: str) -> int:
        """Returns bytes freed. An empty prefix (the root) is refused by `validate_key`."""
        target = self._resolve(prefix)
        freed = self.usage(prefix)
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)
        return freed

    def _files(self, prefix: str) -> Iterator[Path]:
        base = self._resolve(prefix, allow_empty=True)
        if base.is_file():
            yield base
            return
        for dirpath, _dirs, files in os.walk(base, followlinks=False):
            for name in files:
                path = Path(dirpath) / name
                if not path.is_symlink():
                    yield path

    def list(self, prefix: str) -> list[str]:
        return sorted(str(p.relative_to(self.root)) for p in self._files(prefix))

    def usage(self, prefix: str = "") -> int:
        return sum(p.stat().st_size for p in self._files(prefix))

    def local_path(self, key: str) -> Path:
        return self._resolve(key)

    def volume(self) -> tuple[int, int]:
        du = shutil.disk_usage(self.root)
        return du.total, du.free

    def ensure_free_space(self, needed: int) -> None:
        _, free = self.volume()
        if free - needed < self.low_watermark:
            msg = "not enough free disk space"
            raise InsufficientStorage(msg)

    def probe(self) -> None:
        probe = self.root / f"{PROBE_NAME}-{uuid.uuid4().hex}"  # concurrent probes must not collide
        fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(b"ok")
        probe.unlink(missing_ok=True)
        self.ensure_free_space(0)

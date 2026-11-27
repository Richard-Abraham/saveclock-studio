"""Safe download names and file writing (SEC-004): a server-sent name is never used as a path."""

import os
import re
import unicodedata
import urllib.parse
from collections.abc import Iterable
from pathlib import Path

# the extension of each download kind (a test compares the keys with the API's `DownloadKind`)
KIND_EXT = {
    "silent_video": "mp4",
    "cutlist_json": "json",
    "cutlist_csv": "csv",
    "with_song": "mp4",
}
_EXT_STAR = re.compile(r"filename\*\s*=\s*([^;]+)", re.IGNORECASE)
_PLAIN = re.compile(r'filename\s*=\s*("(?:[^"\\]|\\.)*"|[^;]+)', re.IGNORECASE)
_MAX = 120
CHARSET_PARTS = 3  # charset'language'value


def _raw_name(header: str | None) -> str:
    if not header:
        return ""
    star = _EXT_STAR.search(header)
    if star:
        parts = star.group(1).strip().split("'", 2)
        if len(parts) == CHARSET_PARTS:  # charset'language'percent-encoded
            return urllib.parse.unquote(parts[2], encoding="utf-8", errors="replace")
    plain = _PLAIN.search(header)
    if plain:
        return plain.group(1).strip().strip('"').replace('\\"', '"')
    return ""


def safe_name(header: str | None, fallback: str) -> str:
    """A basename that is safe inside any directory: no separators, no control or format
    characters (NUL, the RTL override), no leading dot, at most 120 characters."""
    name = unicodedata.normalize("NFKC", _raw_name(header)).replace("\\", "/").rsplit("/", 1)[-1]
    kept = (c for c in name if not unicodedata.category(c).startswith("C"))
    name = "".join(c if (c.isalnum() or c in " ._-") else "_" for c in kept)
    name = name.strip(" .")[:_MAX].strip(" .")
    return name if name and set(name) != {"_"} else fallback


def target_dir(out: str | None) -> Path:
    directory = Path(out) if out else Path.cwd()
    if not directory.is_dir():
        msg = f"output directory does not exist: {directory}"
        raise NotADirectoryError(msg)
    return directory.resolve()


def write_stream(chunks: Iterable[bytes], directory: Path, name: str, *, force: bool) -> Path:
    """Write to a private temp file, then rename: no partial file, mode 0600."""
    dest = directory / name
    if dest.exists() and not force:
        raise FileExistsError(str(dest))
    tmp = directory / f".{name}.{os.getpid()}.part"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            for chunk in chunks:
                fh.write(chunk)
        # shortcut: check-then-rename is not atomic against a racing writer; upgrade if the
        # tool ever serves more than one local user
        tmp.replace(dest)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return dest

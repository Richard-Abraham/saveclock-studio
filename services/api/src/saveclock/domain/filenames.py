"""Filename hygiene (SEC-004): a client filename is display text, never a path or argument."""

import re
import unicodedata

MAX_NAME = 120
MAX_TITLE = 80
_BIDI = dict.fromkeys([*range(0x202A, 0x202F), *range(0x2066, 0x206A)])
_BAD = re.compile(r"[\\/\x00-\x1f\x7f]")
_SPACES = re.compile(r"\s+")


def normalise(name: str) -> str:
    """NFC, no separators, controls or bidi overrides, single spaces, at most 120 characters."""
    text = unicodedata.normalize("NFC", name).translate(_BIDI)
    text = _SPACES.sub(" ", _BAD.sub(" ", text)).strip(" .")
    return (text or "untitled")[:MAX_NAME]


def ext_of(name: str) -> str:
    """Lowercase extension without the dot, or an empty string."""
    stem, dot, ext = normalise(name).rpartition(".")
    return ext.lower() if dot and stem else ""


def display_title(name: str) -> str:
    clean = normalise(name)
    stem = clean.rpartition(".")[0] if ext_of(clean) else clean
    return (stem or clean)[:MAX_TITLE]

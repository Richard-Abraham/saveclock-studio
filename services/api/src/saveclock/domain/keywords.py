"""Stock-search keywords: validation, the analysis summary that may leave the machine, the ladder.

Pure: no I/O. `AnalysisSummary` is the only analysis data any model ever sees (SEC-169).
"""

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

KEYWORD_RE = re.compile(r"^[a-z][a-z \-]{1,30}$")
MAX_KEYWORDS = 8
MAX_VIBE_CHARS = 100  # SEC-040: the stored hint is up to 200, a prompt gets 100
MAX_SECTIONS = 12
TEMPO_EDGES = (90.0, 120.0, 150.0)  # slow | mid | fast | vfast
TEMPO_BUCKETS = ("slow", "mid", "fast", "vfast")
ENERGY_EDGES = (0.33, 0.66)  # low | mid | high
ENERGY_BUCKETS = ("low", "mid", "high")
DEFAULT_STYLE = "default"


class KeywordSource(StrEnum):
    EXPLICIT = "explicit"
    LLM = "llm"
    TABLE = "table"


def normalize_keyword(raw: object) -> str | None:
    """Lower-case, trim and collapse spaces; None unless the result matches the keyword rule."""
    if not isinstance(raw, str):
        return None
    cleaned = " ".join(raw.lower().split())
    return cleaned if KEYWORD_RE.fullmatch(cleaned) else None


def clean_keywords(raw: Iterable[object]) -> list[str]:
    """Valid keywords in the given order, without duplicates, at most `MAX_KEYWORDS`."""
    out: list[str] = []
    for item in raw:
        kw = normalize_keyword(item)
        if kw is not None and kw not in out:
            out.append(kw)
        if len(out) == MAX_KEYWORDS:
            break
    return out


def tempo_bucket(bpm: float) -> str:
    return TEMPO_BUCKETS[sum(bpm >= edge for edge in TEMPO_EDGES)]


def energy_bucket(mean_energy: float) -> str:
    return ENERGY_BUCKETS[sum(mean_energy >= edge for edge in ENERGY_EDGES)]


@dataclass(frozen=True)
class SectionSummary:
    label: str
    duration_s: float


@dataclass(frozen=True)
class AnalysisSummary:
    tempo_bucket: str
    energy_bucket: str
    sections: tuple[SectionSummary, ...]
    style: str
    vibe: str | None


def clean_vibe(vibe: str | None) -> str | None:
    """Control characters (newlines included) become spaces; at most `MAX_VIBE_CHARS` remain."""
    if vibe is None:
        return None
    spaced = "".join(" " if unicodedata.category(c).startswith("C") else c for c in vibe)
    text = " ".join(spaced.split())[:MAX_VIBE_CHARS].strip()
    return text or None


def summary_from_analysis(
    tempo_bpm: float,
    energy_curve: Sequence[float],
    sections: Sequence[tuple[str, float]],
    *,
    style: str = DEFAULT_STYLE,
    vibe: str | None = None,
) -> AnalysisSummary:
    """`sections` are (label, duration in seconds); the energy curve is 10 Hz in [0, 1]."""
    mean = sum(energy_curve) / len(energy_curve) if energy_curve else 0.0
    return AnalysisSummary(
        tempo_bucket=tempo_bucket(tempo_bpm),
        energy_bucket=energy_bucket(mean),
        sections=tuple(SectionSummary(label, round(d, 1)) for label, d in sections[:MAX_SECTIONS]),
        style=style,
        vibe=clean_vibe(vibe),
    )


def broaden(query: str, fallback: Sequence[str] = ()) -> list[str]:
    """The ladder for a keyword with few results (ARCH §16): the query, its last two words, its
    last word, then the section-agnostic fallback list."""
    words = query.split()
    steps = [query, " ".join(words[-2:]), words[-1] if words else query, *fallback]
    out: list[str] = []
    for step in steps:
        if step and step not in out:
            out.append(step)
    return out

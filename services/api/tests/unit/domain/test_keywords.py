import pytest

from saveclock.domain.keywords import (
    KEYWORD_RE,
    MAX_KEYWORDS,
    MAX_VIBE_CHARS,
    broaden,
    clean_keywords,
    clean_vibe,
    energy_bucket,
    normalize_keyword,
    summary_from_analysis,
    tempo_bucket,
)
from saveclock.domain.keywords_fallback import TABLE, table_keywords


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("neon city", "neon city"),
        ("Neon", "neon"),
        ("  Rainy   Street ", "rainy street"),
        ("time-lapse", "time-lapse"),
        ("a", None),
        ("x" * 40, None),
        ("city; rm -rf", None),
        ("https://evil.example/x", None),
        ("two\nlines", "two lines"),
        ("digits 123", None),
        ("-leading", None),
        ("", None),
        (7, None),
        (None, None),
    ],
)
def test_keyword_accept_reject_table(raw: object, expected: str | None) -> None:
    assert normalize_keyword(raw) == expected


def test_clean_keywords_dedupes_keeps_order_and_caps_at_eight() -> None:
    raw = ["Neon", "neon", "a", *[f"word{chr(97 + i)}" for i in range(12)]]
    out = clean_keywords(raw)
    assert out[0] == "neon"
    assert "a" not in out
    assert len(out) == MAX_KEYWORDS
    assert len(set(out)) == len(out)


@pytest.mark.parametrize(
    ("bpm", "bucket"),
    [
        (89.9, "slow"),
        (90.0, "mid"),
        (119.9, "mid"),
        (120.0, "fast"),
        (149.9, "fast"),
        (150.0, "vfast"),
    ],
)
def test_tempo_bucket_edges(bpm: float, bucket: str) -> None:
    assert tempo_bucket(bpm) == bucket


@pytest.mark.parametrize(
    ("energy", "bucket"),
    [(0.0, "low"), (0.329, "low"), (0.33, "mid"), (0.659, "mid"), (0.66, "high")],
)
def test_energy_bucket_edges(energy: float, bucket: str) -> None:
    assert energy_bucket(energy) == bucket


def test_every_table_row_has_ten_unique_valid_keywords_and_all_buckets_exist() -> None:
    assert len(TABLE) == 12
    for energy in ("low", "mid", "high"):
        for tempo in ("slow", "mid", "fast", "vfast"):
            row = TABLE[(energy, tempo, "default")]
            assert len(row) == 10
            assert len(set(row)) == 10
            assert all(KEYWORD_RE.fullmatch(k) for k in row)


def test_the_two_rows_the_plan_spells_out() -> None:
    assert table_keywords("high", "fast")[:3] == ("neon city night", "fireworks", "crowd lights")
    assert table_keywords("low", "slow")[-1] == "night sky"


def test_unknown_style_uses_the_default_row() -> None:
    assert table_keywords("mid", "mid", "jazz") == table_keywords("mid", "mid", "default")


def test_vibe_is_truncated_stripped_of_control_characters_and_emptied() -> None:
    assert clean_vibe(None) is None
    assert clean_vibe("   \n\t ") is None
    out = clean_vibe("calm\nand\x00 dark " + "x" * 300)
    assert out is not None
    assert len(out) <= MAX_VIBE_CHARS
    assert out.startswith("calm and dark")
    assert "\n" not in out
    assert "\x00" not in out


def test_summary_from_analysis_buckets_and_caps_sections() -> None:
    s = summary_from_analysis(128.0, [0.9, 0.8], [("quiet", 12.34)] * 20, style="rock", vibe="warm")
    assert (s.tempo_bucket, s.energy_bucket, s.style, s.vibe) == ("fast", "high", "rock", "warm")
    assert len(s.sections) == 12
    assert s.sections[0].duration_s == 12.3
    assert summary_from_analysis(80.0, [], []).energy_bucket == "low"


def test_broaden_ladder_in_order_without_duplicates() -> None:
    assert broaden("neon city night", ["fireworks"]) == [
        "neon city night",
        "city night",
        "night",
        "fireworks",
    ]
    assert broaden("fireworks", ["fireworks", "lights"]) == ["fireworks", "lights"]
    assert broaden("", ["x"]) == ["x"]

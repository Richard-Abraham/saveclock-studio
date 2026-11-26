import pytest

from saveclock.domain.filenames import display_title, ext_of, normalise

HOSTILE = [
    "../../etc/passwd",
    "..\\..\\windows\\system32",
    "a" + chr(0x202E) + "b.mp3",
    "a" + chr(0x2066) + "b" + chr(0x2069) + ".wav",
    "nul\x00byte\x01\x1f.mp3",
    "x" * 500 + ".mp3",
    "....",
    "////",
    "",
    "   ",
    "line\nbreak\r\ntab\t.wav",
    "e" + chr(0x301) + ".mp3",
]


@pytest.mark.parametrize("name", HOSTILE)
def test_hostile_names_come_out_safe(name: str) -> None:
    out = normalise(name)
    assert out
    assert len(out) <= 120
    assert "/" not in out
    assert "\\" not in out
    assert not any(ord(c) < 32 or ord(c) == 127 for c in out)
    assert not any(0x202A <= ord(c) <= 0x202E or 0x2066 <= ord(c) <= 0x2069 for c in out)
    assert len(display_title(name)) <= 80


def test_nfc_and_whitespace() -> None:
    assert normalise("e" + chr(0x301) + "  x.mp3") == chr(0xE9) + " x.mp3"


def test_extension_and_title() -> None:
    assert ext_of("My Song.MP3") == "mp3"
    assert ext_of("noext") == ""
    assert ext_of(".mp3") == ""
    assert display_title("My Song.mp3") == "My Song"
    assert display_title("noext") == "noext"
    assert len(display_title("a" * 200 + ".wav")) == 80

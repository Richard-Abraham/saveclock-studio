"""The pure upload header rules (the HTTP behaviour is tested in tests/integration)."""

import pytest

from saveclock.errors import BadRequest, PayloadTooLarge
from saveclock.services.ingest import declared_length, decode_filename

CAP = 100 * 1024 * 1024


def test_declared_length_accepts_the_limit_and_zero() -> None:
    assert declared_length("1234", CAP) == 1234
    assert declared_length(str(CAP), CAP) == CAP
    assert declared_length("0", CAP) == 0


@pytest.mark.parametrize("header", [None, "", "abc", "-1", "12.5", "1e3"])
def test_declared_length_is_required_and_numeric(header: str | None) -> None:
    with pytest.raises(BadRequest) as err:
        declared_length(header, CAP)
    assert err.value.details == {"reason": "content_length_required"}


def test_declared_length_over_the_cap_is_413_before_any_read() -> None:
    with pytest.raises(PayloadTooLarge):
        declared_length(str(CAP + 1), CAP)


def test_filename_is_percent_decoded_then_normalised() -> None:
    assert decode_filename("My%20Song%20%C3%A9.mp3") == "My Song é.mp3"
    assert decode_filename("..%2F..%2Fetc%2Fpasswd") == "etc passwd"
    assert decode_filename(None) == "untitled"
    assert decode_filename("%00%1f.wav") == "wav"  # controls and leading dots are stripped


def test_a_bad_percent_sequence_is_a_bad_request() -> None:
    with pytest.raises(BadRequest) as err:
        decode_filename("%ff%fe.wav")
    assert err.value.details == {"reason": "bad_filename"}

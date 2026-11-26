import pytest

from saveclock.domain.ids import derive_job_id
from saveclock.domain.media_sniff import ALLOWED_EXT, MIME_TO_FMT, MP4_FMT, NotSniffable, sniff

HEADS = {
    "mp3": [b"ID3\x04\x00\x00\x00\x00\x00\x00", b"\xff\xfb\x90\x00" + b"\x00" * 12],
    "wav": [b"RIFF\x24\x08\x00\x00WAVEfmt "],
    "flac": [b"fLaC\x00\x00\x00\x22" + b"\x00" * 8],
    "ogg": [b"OggS\x00\x02" + b"\x00" * 10],
    MP4_FMT: [b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 4],
}


@pytest.mark.parametrize(("fmt", "heads"), HEADS.items())
def test_one_real_header_per_format(fmt: str, heads: list[bytes]) -> None:
    for head in heads:
        assert sniff(head).fmt == fmt
        assert sniff(head).ext in ALLOWED_EXT[fmt]


def test_raw_adts_is_rejected() -> None:
    # 0xFF 0xF1: sync bits set, layer 00 (AAC ADTS). An MPEG test on the sync alone calls it mp3.
    with pytest.raises(NotSniffable):
        sniff(bytes.fromhex("fff15080") + b"\x00" * 12)


@pytest.mark.parametrize(
    "head",
    [b"#EXTM3U\n#EXT-X-VERSION:3", b"", b"\xff", b"RIFF\x00\x00\x00\x00AVI LIST", b"MZ\x90\x00"],
)
def test_everything_else_is_unsupported(head: bytes) -> None:
    with pytest.raises(NotSniffable):
        sniff(head)


def test_mime_table_points_at_known_formats() -> None:
    assert set(MIME_TO_FMT.values()) <= set(ALLOWED_EXT)


def test_derived_job_ids_are_stable_and_distinct() -> None:
    from uuid import UUID

    parent = UUID("00000000-0000-4000-8000-000000000001")
    assert derive_job_id(parent, "analyze") == derive_job_id(parent, "analyze")
    assert derive_job_id(parent, "analyze") != derive_job_id(parent, "draft")

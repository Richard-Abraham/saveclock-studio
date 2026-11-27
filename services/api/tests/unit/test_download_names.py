"""The download name (RFC 6266, SEC-004): `serve(download_name=...)` and the slug of a title."""

from pathlib import Path
from uuid import UUID

import pytest

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.domain.render_job import DownloadKind
from saveclock.services.downloads import MAX_SLUG, download_name, slug_of
from saveclock.services.files import serve

PID = UUID("22222222-2222-4222-8222-222222222222")


def disposition(tmp_path: Path, name: str | None) -> str:
    store = FilesystemBlobStore(tmp_path, low_watermark_gb=0)
    key = f"renders/{PID}/master.mp4"
    store.put(key, iter([b"x"]), max_bytes=10)
    return serve(store, key, None, download_name=name).headers["content-disposition"]


def test_an_ascii_name_is_the_fallback_and_the_encoded_name(tmp_path: Path) -> None:
    assert disposition(tmp_path, "my-song-silent_video.mp4") == (
        'attachment; filename="my-song-silent_video.mp4"; '
        "filename*=UTF-8''my-song-silent_video.mp4"
    )


def test_a_non_ascii_title_keeps_its_letters_only_in_the_encoded_name(tmp_path: Path) -> None:
    got = disposition(tmp_path, "Café Été-silent_video.mp4")
    assert 'filename="Caft-silent_video.mp4"' in got
    assert "filename*=UTF-8''Caf%C3%A9%20%C3%89t%C3%A9-silent_video.mp4" in got
    assert got.isascii()


@pytest.mark.parametrize(
    "evil",
    ['a"b.mp4', "a\r\nSet-Cookie: x=1.mp4", "a\nb.mp4", "..\\..\\x.mp4", "a;b=c.mp4"],
)
def test_quotes_and_line_breaks_cannot_leave_the_header_value(tmp_path: Path, evil: str) -> None:
    got = disposition(tmp_path, evil)
    assert "\r" not in got
    assert "\n" not in got
    fallback = got.split('filename="', 1)[1].split('"', 1)[0]
    assert all(c.isalnum() or c in "._-" for c in fallback)
    assert got.count('"') == 2
    assert got.isascii()


def test_a_name_with_nothing_ascii_falls_back_to_download(tmp_path: Path) -> None:
    got = disposition(tmp_path, "日本語")
    assert 'filename="download"' in got
    assert "filename*=UTF-8''%E6%97%A5%E6%9C%AC%E8%AA%9E" in got


def test_without_a_download_name_the_blob_name_is_used_as_before(tmp_path: Path) -> None:
    assert disposition(tmp_path, None) == 'attachment; filename="master.mp4"'


# --- the slug of a project title ---------------------------------------------------------------


def test_a_title_becomes_a_slug_with_the_kind_and_extension() -> None:
    assert slug_of("My Song 2", PID) == "My-Song-2"
    assert (
        download_name("My Song 2", PID, DownloadKind.SILENT_VIDEO) == "My-Song-2-silent_video.mp4"
    )
    assert download_name("x", PID, DownloadKind.CUTLIST_JSON) == "x-cutlist_json.json"
    assert download_name("x", PID, DownloadKind.CUTLIST_CSV) == "x-cutlist_csv.csv"
    assert download_name("x", PID, DownloadKind.WITH_SONG) == "x-with_song.mp4"


@pytest.mark.parametrize("title", [None, "", "   ", '""', "- -"])
def test_an_unusable_title_falls_back_to_the_render_id(title: str | None) -> None:
    assert slug_of(title, PID) == "saveclock-22222222"


def test_a_title_of_only_separators_is_the_normalised_untitled() -> None:
    assert slug_of("///", PID) == "untitled"  # `normalise` names a nameless title this way


def test_separators_quotes_and_controls_are_removed_from_a_title() -> None:
    slug = slug_of('a/b\\c:"d"\r\ne', PID)
    assert not any(c in slug for c in '/\\:"\r\n ')
    assert slug_of("日本語の歌", PID) == "日本語の歌"  # kept: the encoded name carries it


def test_a_long_title_is_cut() -> None:
    assert len(slug_of("x" * 500, PID)) == MAX_SLUG
    assert slug_of("a" * 59 + " b", PID) == "a" * 59  # no dangling separator at the cut

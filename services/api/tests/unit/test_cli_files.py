"""SEC-004 for the CLI: a server-sent name is never a path; files are private, not overwritten."""

import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

from saveclock.cli import files
from saveclock.domain.render_job import DownloadKind

FALLBACK = "rid-silent_video.mp4"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ('attachment; filename="../../etc/passwd"', "passwd"),
        ('attachment; filename="a/b.mp4"', "b.mp4"),
        ('attachment; filename="C:\\x.mp4"', "x.mp4"),
        ('attachment; filename="a\x00b\x07.mp4"', "ab.mp4"),
        ('attachment; filename="clip\u202etxt.mp4"', "cliptxt.mp4"),
        (
            "attachment; filename*=UTF-8''night%20drive%E2%80%A6.mp4",
            "night drive....mp4",
        ),  # NFKC turns the ellipsis into dots
        ("attachment; filename*=UTF-8''%2e%2e%2fevil.mp4", "evil.mp4"),
        ('attachment; filename=""', FALLBACK),
        ("attachment", FALLBACK),
        (None, FALLBACK),
        ('attachment; filename=".."', FALLBACK),
        ('attachment; filename=".hidden"', "hidden"),
    ],
)
def test_the_server_name_becomes_a_safe_basename(header: str | None, expected: str) -> None:
    name = files.safe_name(header, FALLBACK)
    assert name == expected
    assert not {"/", "\\", "\x00"} & set(name)


@pytest.mark.unit
def test_a_very_long_name_is_cut() -> None:
    assert len(files.safe_name(f'attachment; filename="{"a" * 500}.mp4"', FALLBACK)) <= 120


@pytest.mark.unit
def test_a_traversal_name_lands_inside_the_output_directory(tmp_path: Path) -> None:
    name = files.safe_name('attachment; filename="../../../x.bin"', FALLBACK)
    dest = files.write_stream([b"x"], tmp_path, name, force=False)
    assert dest.parent == tmp_path
    assert dest.read_bytes() == b"x"


@pytest.mark.unit
def test_an_existing_file_is_not_overwritten_without_force(tmp_path: Path) -> None:
    (tmp_path / "a.mp4").write_bytes(b"old")
    with pytest.raises(FileExistsError):
        files.write_stream([b"new"], tmp_path, "a.mp4", force=False)
    assert (tmp_path / "a.mp4").read_bytes() == b"old"
    files.write_stream([b"new"], tmp_path, "a.mp4", force=True)
    assert (tmp_path / "a.mp4").read_bytes() == b"new"


@pytest.mark.unit
def test_the_file_is_private_and_no_partial_file_is_left(tmp_path: Path) -> None:
    old = os.umask(0)  # a permissive umask must not widen the mode
    try:
        dest = files.write_stream([b"x"], tmp_path, "a.mp4", force=False)
    finally:
        os.umask(old)
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600

    def broken() -> Iterator[bytes]:
        yield b"x"
        raise OSError("disk gone")

    with pytest.raises(OSError, match="disk gone"):
        files.write_stream(broken(), tmp_path, "b.mp4", force=False)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.mp4"]


@pytest.mark.unit
def test_the_output_directory_must_exist(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        files.target_dir(str(tmp_path / "missing"))


@pytest.mark.unit
def test_every_download_kind_has_an_extension() -> None:
    assert set(files.KIND_EXT) == {k.value for k in DownloadKind}

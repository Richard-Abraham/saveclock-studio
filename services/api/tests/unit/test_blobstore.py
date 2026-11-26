"""BlobStore through its public interface. The contract class takes every implementation."""

import os
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest

from saveclock.adapters.blobstore.blob_keys import (
    InvalidKey,
    is_servable,
    render_file_key,
    song_incoming_key,
    song_source_key,
    stub_key,
    validate_key,
    work_key,
)
from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.blobstore.port import BlobStore
from saveclock.errors import InsufficientStorage, NotFound, PayloadTooLarge

PID = UUID("11111111-1111-4111-8111-111111111111")

TRAVERSAL_CORPUS = [
    "",
    "/etc/passwd",
    "../x",
    "a/../../x",
    "a/./b",
    "a//b",
    "a\\b",
    "a\x00b",
    "songs/%2e%2e/x",
    "a" * 600,
    "．．/x",  # noqa: RUF001 - fullwidth dots on purpose
]


@pytest.fixture(params=["filesystem"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> BlobStore:
    # a later S3 stub joins here by adding a param
    root = tmp_path / "root"
    root.mkdir()
    return FilesystemBlobStore(root, low_watermark_gb=0)


def chunks(data: bytes, size: int = 3) -> Iterator[bytes]:
    for i in range(0, len(data), size):
        yield data[i : i + size]


@pytest.mark.unit
@pytest.mark.parametrize("key", TRAVERSAL_CORPUS)
def test_traversal_corpus_is_rejected(store: BlobStore, key: str, tmp_path: Path) -> None:
    with pytest.raises(InvalidKey):
        validate_key(key)
    for call in (
        lambda: store.stat(key),
        lambda: store.put(key, iter([b"x"]), max_bytes=10),
        lambda: store.delete(key),
        lambda: store.open(key),
    ):
        with pytest.raises(InvalidKey):
            call()
    assert list(tmp_path.iterdir()) == [tmp_path / "root"]
    assert list((tmp_path / "root").iterdir()) == []


@pytest.mark.unit
def test_key_builders() -> None:
    assert song_source_key(PID, "mp3") == f"songs/{PID}/source.mp3"
    assert song_incoming_key(PID) == f"songs/{PID}/incoming.bin"
    assert work_key(PID, "raw", "pexels_1.mp4") == f"work/{PID}/raw/pexels_1.mp4"
    assert render_file_key(PID, "master.mp4") == f"renders/{PID}/master.mp4"
    assert stub_key(PID) == f"renders/{PID}/stub.txt"
    with pytest.raises(InvalidKey):
        song_source_key(PID, "../x")
    with pytest.raises(InvalidKey):
        render_file_key(PID, "evil.sh")
    with pytest.raises(InvalidKey):
        work_key(PID, "..", "x")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("key", "servable"),
    [
        (f"renders/{PID}/master.mp4", True),
        (f"renders/{PID}/stub.txt", True),
        (f"renders/{PID}/cutlist.csv", True),
        (f"work/{PID}/proxy/pexels_9.mp4", True),
        (f"work/{PID}/audio_proxy.m4a", True),
        (f"songs/{PID}/source.mp3", False),
        (f"songs/{PID}/incoming.bin", False),
        (f"work/{PID}/raw/x.mp4", False),
        (f"work/{PID}/mezz/x.mp4", False),
        (f"renders/{PID}/other.bin", False),
        ("renders/not-a-uuid/master.mp4", False),
        (f"renders/{PID}/../{PID}/master.mp4", False),
    ],
)
def test_is_servable_allowlist(key: str, servable: bool) -> None:
    assert is_servable(key) is servable


@pytest.mark.unit
def test_put_open_stat_roundtrip_with_modes(store: BlobStore, tmp_path: Path) -> None:
    key = f"songs/{PID}/incoming.bin"
    assert store.put(key, chunks(b"0123456789"), max_bytes=1000) == 10
    assert b"".join(store.open(key)) == b"0123456789"
    assert store.stat(key).size == 10
    assert store.exists(key)
    path = tmp_path / "root" / key
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert oct(path.parent.stat().st_mode & 0o777) == "0o700"
    assert oct(path.parent.parent.stat().st_mode & 0o777) == "0o700"
    assert not list(path.parent.glob("*.part"))


@pytest.mark.unit
def test_range_is_inclusive(store: BlobStore) -> None:
    store.put("renders/a/x.txt", iter([b"0123456789"]), max_bytes=100)
    assert b"".join(store.open("renders/a/x.txt", (2, 5))) == b"2345"


@pytest.mark.unit
def test_put_over_cap_leaves_nothing(store: BlobStore, tmp_path: Path) -> None:
    with pytest.raises(PayloadTooLarge):
        store.put("songs/a/incoming.bin", iter([b"x" * 1000]), max_bytes=999)
    assert not store.exists("songs/a/incoming.bin")
    assert [p for p in (tmp_path / "root").rglob("*") if p.is_file()] == []


@pytest.mark.unit
def test_put_cap_is_enforced_across_chunks(store: BlobStore, tmp_path: Path) -> None:
    with pytest.raises(PayloadTooLarge):
        store.put("songs/a/incoming.bin", chunks(b"x" * 100, 10), max_bytes=55)
    assert [p for p in (tmp_path / "root").rglob("*") if p.is_file()] == []


@pytest.mark.unit
def test_crash_inside_the_stream_leaves_no_final_file(store: BlobStore, tmp_path: Path) -> None:
    def broken() -> Iterator[bytes]:
        yield b"abc"
        msg = "client went away"
        raise ConnectionError(msg)

    with pytest.raises(ConnectionError):
        store.put("songs/a/incoming.bin", broken(), max_bytes=100)
    assert not store.exists("songs/a/incoming.bin")
    assert [p for p in (tmp_path / "root").rglob("*") if p.is_file()] == []


@pytest.mark.unit
def test_put_replaces_atomically(store: BlobStore) -> None:
    store.put("renders/a/x.txt", iter([b"one"]), max_bytes=100)
    store.put("renders/a/x.txt", iter([b"two!"]), max_bytes=100)
    assert b"".join(store.open("renders/a/x.txt")) == b"two!"


@pytest.mark.unit
def test_symlinked_file_is_refused(store: BlobStore, tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"secret")
    (tmp_path / "root" / "renders").mkdir()
    (tmp_path / "root" / "renders" / "link.txt").symlink_to(outside)
    for call in (
        lambda: store.stat("renders/link.txt"),
        lambda: store.open("renders/link.txt"),
        lambda: store.put("renders/link.txt", iter([b"x"]), max_bytes=10),
        lambda: store.delete("renders/link.txt"),
    ):
        with pytest.raises((InvalidKey, NotFound)):
            call()
    assert outside.read_bytes() == b"secret"


@pytest.mark.unit
def test_symlinked_directory_component_is_refused(store: BlobStore, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "f.txt").write_bytes(b"secret")
    (tmp_path / "root" / "work").symlink_to(outside)
    with pytest.raises(InvalidKey):
        store.stat("work/f.txt")
    with pytest.raises(InvalidKey):
        store.put("work/new.txt", iter([b"x"]), max_bytes=10)
    assert not (outside / "new.txt").exists()


@pytest.mark.unit
def test_missing_blob_is_not_found(store: BlobStore) -> None:
    with pytest.raises(NotFound):
        store.stat("renders/a/none.txt")
    with pytest.raises(NotFound):
        store.open("renders/a/none.txt")
    assert not store.exists("renders/a/none.txt")


@pytest.mark.unit
def test_delete_prefix_usage_and_list(store: BlobStore, tmp_path: Path) -> None:
    store.put("work/p1/a.bin", iter([b"aaaa"]), max_bytes=10)
    store.put("work/p1/sub/b.bin", iter([b"bb"]), max_bytes=10)
    store.put("work/p2/c.bin", iter([b"c"]), max_bytes=10)
    assert store.usage("work/p1") == 6
    assert store.usage() == 7
    assert store.list("work/p1") == ["work/p1/a.bin", "work/p1/sub/b.bin"]
    assert store.delete_prefix("work/p1") == 6
    assert store.list("work") == ["work/p2/c.bin"]
    assert store.usage("nothing/here") == 0
    store.delete("work/p2/c.bin")
    store.delete("work/p2/c.bin")  # idempotent
    assert store.list("work") == []


@pytest.mark.unit
@pytest.mark.parametrize("prefix", ["", "/", "..", "a/../..", "/etc"])
def test_delete_prefix_refuses_root_and_escapes(store: BlobStore, prefix: str) -> None:
    store.put("keep/x.bin", iter([b"x"]), max_bytes=10)
    with pytest.raises(InvalidKey):
        store.delete_prefix(prefix)
    assert store.exists("keep/x.bin")


@pytest.mark.unit
def test_free_space_guard(tmp_path: Path) -> None:
    tight = FilesystemBlobStore(tmp_path, low_watermark_gb=10**9)
    with pytest.raises(InsufficientStorage):
        tight.ensure_free_space(0)
    with pytest.raises(InsufficientStorage):
        tight.probe()
    FilesystemBlobStore(tmp_path, low_watermark_gb=0).ensure_free_space(1)


@pytest.mark.unit
def test_probe_fails_on_read_only_root(tmp_path: Path) -> None:
    root = tmp_path / "ro"
    root.mkdir()
    store = FilesystemBlobStore(root, low_watermark_gb=0)
    store.probe()
    root.chmod(0o500)
    try:
        if os.geteuid() == 0:
            pytest.skip("root ignores directory permissions")
        with pytest.raises(PermissionError):
            store.probe()
    finally:
        root.chmod(0o700)


@pytest.mark.unit
def test_stat_of_a_directory_is_not_found(store: BlobStore) -> None:
    store.put("work/p1/a.bin", iter([b"a"]), max_bytes=10)
    with pytest.raises(NotFound):
        store.stat("work/p1")


@pytest.mark.unit
def test_prefix_operations_on_a_single_file(store: BlobStore, tmp_path: Path) -> None:
    store.put("work/p1/a.bin", iter([b"abc"]), max_bytes=10)
    assert store.list("work/p1/a.bin") == ["work/p1/a.bin"]
    assert store.usage("work/p1/a.bin") == 3
    assert store.delete_prefix("work/p1/a.bin") == 3
    assert not store.exists("work/p1/a.bin")


@pytest.mark.unit
def test_local_path_stays_under_the_root(store: BlobStore, tmp_path: Path) -> None:
    assert store.local_path("work/p1/a.bin") == tmp_path / "root" / "work/p1/a.bin"
    with pytest.raises(InvalidKey):
        store.local_path("../x")


@pytest.mark.unit
def test_walks_ignore_symlinks(store: BlobStore, tmp_path: Path) -> None:
    store.put("work/p1/a.bin", iter([b"abc"]), max_bytes=10)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"x" * 100)
    (tmp_path / "root" / "work" / "p1" / "link.bin").symlink_to(outside)
    assert store.usage() == 3
    assert store.list("work") == ["work/p1/a.bin"]


@pytest.mark.unit
def test_containment_backstop_refuses_a_resolved_path_outside_the_root(
    store: BlobStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No symlink is involved here: the realpath check is a second line of defence.
    monkeypatch.setattr(os.path, "realpath", lambda _p: "/elsewhere")
    with pytest.raises(InvalidKey):
        store.stat("work/p1/a.bin")

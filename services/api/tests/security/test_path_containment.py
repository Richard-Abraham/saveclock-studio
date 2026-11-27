"""Path containment (plan 008, T-2.14; SEC-160): no key, id or query value can leave `BLOB_ROOT`,
and what is never served (the song, the upload, the intermediates) is never served."""

import os
from pathlib import Path
from urllib.parse import quote, urlsplit
from uuid import UUID

import pytest

from saveclock.adapters.blobstore.blob_keys import InvalidKey, is_servable, validate_key
from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.errors import NotFound
from tests.integration.conftest import ApiEnv
from tests.integration.housekeeping_harness import Hk

pytestmark = [pytest.mark.security, pytest.mark.integration]
CANARY_TEXT = b"outside-the-blob-root-canary"
ROUTES = (
    "/api/v1/projects/{x}/credits",
    "/api/v1/projects/{x}/events",
    "/api/v1/projects/{x}",
    "/api/v1/renders/{x}",
    "/api/v1/renders/{x}/download?kind=silent_video",
)
# plan 001's corpus, extended: parent traversal, encodings, absolute, backslash, NUL, odd forms
HOSTILE = [
    "..",
    "../..",
    "../../etc/passwd",
    "%2e%2e",
    "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    "%252e%252e%252f",  # double encoding
    "/etc/passwd",
    "..\\..\\etc\\passwd",
    "a\x00b",
    "renders/../../etc/passwd",
    "work/./../../x",
    "songs//x",
    "x" * 300,
    "..;/",
    "~",
    "$(id)",
]
NEVER_SERVED = [
    "songs/{pid}/source.wav",
    "songs/{pid}/source.mp3",
    "songs/{pid}/incoming.bin",
    "songs/{pid}/incoming.bin.part",
    "work/{pid}/raw/pexels_1.mp4",
    "work/{pid}/mezz/pexels_1.mp4",
    "work/{pid}/emb/pexels_1.npy",
    "work/{pid}/canonical.flac",
]


@pytest.mark.parametrize("key", HOSTILE)
def test_no_hostile_key_is_valid_or_servable(key: str) -> None:
    with pytest.raises(InvalidKey):
        validate_key(key)
    assert is_servable(key) is False


@pytest.mark.parametrize("template", NEVER_SERVED)
def test_songs_and_intermediates_are_never_servable(template: str) -> None:
    key = template.format(pid=UUID(int=5))
    assert is_servable(key) is False


def test_a_symlink_inside_the_root_cannot_reach_outside(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "canary.txt").write_bytes(CANARY_TEXT)
    (root / "renders").mkdir()
    os.symlink(outside, root / "renders" / "dir")  # a directory link
    os.symlink(outside / "canary.txt", root / "renders" / "file")  # a file link
    store = FilesystemBlobStore(root, 0)
    for key in ("renders/dir/canary.txt", "renders/file"):
        with pytest.raises((InvalidKey, NotFound)):
            b"".join(store.open(key))
        with pytest.raises((InvalidKey, NotFound)):
            store.stat(key)
        with pytest.raises(InvalidKey):
            store.local_path(key)
    assert (outside / "canary.txt").read_bytes() == CANARY_TEXT


def test_a_key_that_resolves_outside_after_normalisation_is_refused(tmp_path: Path) -> None:
    store = FilesystemBlobStore(tmp_path / "root", 0)
    for key in ("renders/a/../../../x", "renders/%2e%2e/x", "work/..", "./x"):
        with pytest.raises(InvalidKey):
            store.local_path(key)
        with pytest.raises(InvalidKey):
            store.delete(key)


@pytest.mark.parametrize("value", HOSTILE)
async def test_no_route_leaks_or_escapes_for_a_hostile_id(
    hk: Hk, api: ApiEnv, tmp_path: Path, value: str
) -> None:
    canary = tmp_path / "canary.txt"
    canary.write_bytes(CANARY_TEXT)
    before = sorted(str(p.relative_to(api.blob_root)) for p in api.blob_root.rglob("*"))
    for template in ROUTES:
        url = template.format(x=quote(value, safe=""))
        response = await api.client.get(url)
        if response.status_code in {307, 308}:  # a trailing-slash redirect: it must stay in the API
            assert urlsplit(response.headers["location"]).path.startswith("/api/v1/"), url
            continue
        assert response.status_code in {400, 404, 422}, (url, response.status_code)
        assert CANARY_TEXT not in response.content
        assert b"root:x:" not in response.content
    assert canary.read_bytes() == CANARY_TEXT
    after = sorted(str(p.relative_to(api.blob_root)) for p in api.blob_root.rglob("*"))
    assert after == before  # a read route created or removed nothing under the root


async def test_a_hostile_download_kind_is_422_and_a_symlinked_file_is_not_served(
    hk: Hk, api: ApiEnv, tmp_path: Path
) -> None:
    pid = await hk.project(status="ready")
    rid = await hk.render(pid, await hk.plan(pid), mode_a=True)
    canary = tmp_path / "canary.txt"
    canary.write_bytes(CANARY_TEXT)
    await hk.sql("UPDATE renders SET mode_a_state='ready' WHERE id=$1", rid)
    master = api.blob_root / "renders" / str(rid) / "master.mp4"
    master.unlink()
    os.symlink(canary, master)  # the render's own file replaced by a link to the outside
    for kind in ("../../etc/passwd", "silent_video/../x", "master.mp4", "with_song%00", ""):
        response = await api.client.get(f"/api/v1/renders/{rid}/download", params={"kind": kind})
        assert response.status_code == 422, (kind, response.status_code)
    response = await api.client.get(
        f"/api/v1/renders/{rid}/download", params={"kind": "silent_video"}
    )
    assert CANARY_TEXT not in response.content
    # never the canary: a planted link is refused like a missing key
    assert response.status_code == 404
    ok = await api.client.get(f"/api/v1/renders/{rid}/download", params={"kind": "with_song"})
    assert ok.status_code == 200  # the untouched file of the same render still serves


async def test_no_route_serves_the_song_or_an_intermediate_even_when_it_exists(
    hk: Hk, api: ApiEnv
) -> None:
    pid = await hk.project(status="ready")
    rid = await hk.render(pid, await hk.plan(pid), mode_a=True)
    hk.put(f"songs/{pid}/incoming.bin", b"secret-upload")
    secrets = [b"song" * 50, b"x" * 100, b"secret-upload"]  # the bytes the helper wrote
    for url in (
        f"/api/v1/renders/{rid}/download?kind=silent_video",
        f"/api/v1/renders/{rid}/download?kind=with_song",
        f"/api/v1/renders/{rid}/download?kind=cutlist_json",
        f"/api/v1/projects/{pid}/credits",
        f"/api/v1/projects/{pid}",
    ):
        response = await api.client.get(url)
        for secret in secrets:
            assert secret not in response.content, url

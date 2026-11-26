"""POST /projects/{id}/song: every check, in the order the plan gives, with its own test."""

import asyncio
import time
from collections.abc import AsyncIterator, Iterable, Iterator
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

import asyncpg
import pytest

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.services.identity import OWNER_USER_ID
from tests.integration.conftest import ApiEnv, Db, build_api

pytestmark = pytest.mark.integration

WAV = b"RIFF\x24\x08\x00\x00WAVEfmt " + b"\x00" * 4000
MP3 = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 4000
OTHER = UUID("00000000-0000-4000-8000-0000000000bb")


async def make_project(env: ApiEnv) -> str:
    r = await env.client.post("/api/v1/projects", json={})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def song_url(pid: str) -> str:
    return f"/api/v1/projects/{pid}/song"


def headers(name: str = "song.wav", ctype: str = "application/octet-stream") -> dict[str, str]:
    return {"content-type": ctype, "x-filename": quote(name)}


async def sql(db: Db, query: str, *args: object) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(db.raw("postgres"))
    try:
        rows: list[asyncpg.Record] = await conn.fetch(query, *args)
        return rows
    finally:
        await conn.close()


async def status_of(env: ApiEnv, pid: str) -> str:
    return str((await sql(env.db, "SELECT status FROM projects WHERE id = $1", UUID(pid)))[0][0])


def blob_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


async def test_happy_path(api: ApiEnv) -> None:
    pid = await make_project(api)
    r = await api.client.post(song_url(pid), content=WAV, headers=headers("My Song.WAV"))
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["ui_status"] == "analysing"
    assert await status_of(api, pid) == "validating"
    assert (api.blob_root / "songs" / pid / "incoming.bin").read_bytes() == WAV
    song = (await sql(api.db, "SELECT * FROM songs WHERE project_id = $1", UUID(pid)))[0]
    assert (song["original_filename"], song["size_bytes"]) == ("My Song.WAV", len(WAV))
    assert song["content_type"] == "application/octet-stream"
    job = (
        await sql(
            api.db, "SELECT stage, queue, state FROM jobs WHERE id = $1", UUID(body["job_id"])
        )
    )[0]
    assert tuple(job) == ("validate", "analysis", "queued")
    assert api.enqueuer.sent == [("validate_audio", (body["job_id"], str(OWNER_USER_ID)))]
    done = (await sql(api.db, "SELECT upload_completed_at FROM projects WHERE id = $1", UUID(pid)))[
        0
    ]
    assert done[0] is not None


async def test_the_filename_is_display_text_only(api: ApiEnv) -> None:
    pid = await make_project(api)
    r = await api.client.post(
        song_url(pid), content=WAV, headers=headers("../../etc/passwd" + chr(0x202E) + ".wav")
    )
    assert r.status_code == 202
    name = (await sql(api.db, "SELECT original_filename FROM songs"))[0][0]
    assert "/" not in name
    assert chr(0x202E) not in name
    assert [p.relative_to(api.blob_root).as_posix() for p in blob_files(api.blob_root)] == [
        f"songs/{pid}/incoming.bin"
    ]


async def test_missing_content_length_is_a_bad_request(api: ApiEnv) -> None:
    pid = await make_project(api)

    async def chunked() -> AsyncIterator[bytes]:
        yield WAV

    r = await api.client.post(song_url(pid), content=chunked(), headers=headers())
    assert r.status_code == 400
    assert r.json()["error"]["details"]["reason"] == "content_length_required"
    assert await status_of(api, pid) == "created"


async def test_declared_size_over_the_limit_is_refused_before_reading(api: ApiEnv) -> None:
    pid = await make_project(api)
    r = await api.client.post(
        song_url(pid), content=b"x", headers={**headers(), "content-length": "104857601"}
    )
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "payload_too_large"
    assert blob_files(api.blob_root) == []
    assert await status_of(api, pid) == "created"


async def test_a_body_longer_than_declared_is_cut(api: ApiEnv) -> None:
    pid = await make_project(api)
    r = await api.client.post(
        song_url(pid), content=WAV, headers={**headers(), "content-length": "1000"}
    )
    assert r.status_code == 413
    assert blob_files(api.blob_root) == []  # the .part is gone too
    assert await status_of(api, pid) == "created"


async def test_the_byte_cap_comes_from_the_limit_not_the_header(
    migrated_db: Db, blob_root: Path
) -> None:
    async with build_api(migrated_db, blob_root, max_upload_mb=1) as env:
        pid = await make_project(env)
        big = WAV + b"\x00" * (1024 * 1024 + 100)
        r = await env.client.post(
            song_url(pid), content=big, headers={**headers(), "content-length": "1000000"}
        )
        assert r.status_code == 413
        assert blob_files(blob_root) == []
        exact = WAV + b"\x00" * (1024 * 1024 - len(WAV))
        ok = await env.client.post(song_url(pid), content=exact, headers=headers())
        assert ok.status_code == 202  # exactly 1 MB is within the limit


async def test_a_short_body_is_a_bad_request(api: ApiEnv) -> None:
    pid = await make_project(api)
    r = await api.client.post(
        song_url(pid), content=WAV, headers={**headers(), "content-length": str(len(WAV) + 50)}
    )
    assert r.status_code == 400
    assert blob_files(api.blob_root) == []
    assert await status_of(api, pid) == "created"


@pytest.mark.parametrize(
    ("data", "name", "ctype", "reason"),
    [
        (MP3, "song.wav", "application/octet-stream", "extension_mismatch"),
        (WAV, "song.mp3", "application/octet-stream", "extension_mismatch"),
        (WAV, "noext", "application/octet-stream", "extension_mismatch"),
        (WAV, "song.wav", "audio/mpeg", "mime_mismatch"),
        (WAV, "song.wav", "text/plain", "mime_mismatch"),
        (b"#EXTM3U\n" + b"a" * 4000, "song.mp3", "application/octet-stream", "unsniffable"),
        (bytes.fromhex("fff15080") + b"\x00" * 4000, "song.aac", "audio/aac", "unsniffable"),
        (b"", "song.wav", "application/octet-stream", "unsniffable"),
    ],
)
async def test_sniff_extension_and_mime_must_agree(
    api: ApiEnv, data: bytes, name: str, ctype: str, reason: str
) -> None:
    pid = await make_project(api)
    r = await api.client.post(song_url(pid), content=data, headers=headers(name, ctype))
    assert r.status_code == 415, r.text
    assert r.json()["error"]["code"] == "unsupported_media"
    assert r.json()["error"]["details"]["reason"] == reason
    assert blob_files(api.blob_root) == []
    assert await status_of(api, pid) == "created"
    assert api.enqueuer.sent == []


async def test_the_matching_audio_mime_is_accepted(api: ApiEnv) -> None:
    pid = await make_project(api)
    ok = await api.client.post(song_url(pid), content=MP3, headers=headers("a.mp3", "audio/mpeg"))
    assert ok.status_code == 202


async def test_a_bad_filename_encoding_is_a_bad_request(api: ApiEnv) -> None:
    pid = await make_project(api)
    r = await api.client.post(
        song_url(pid), content=WAV, headers={**headers(), "x-filename": "%ff%fe.wav"}
    )
    assert r.status_code == 400
    assert r.json()["error"]["details"]["reason"] == "bad_filename"


async def test_one_upload_at_a_time_per_project(api: ApiEnv) -> None:
    pid = await make_project(api)
    release = asyncio.Event()

    async def slow() -> AsyncIterator[bytes]:
        yield WAV[:2000]
        await release.wait()
        yield WAV[2000:]

    first = asyncio.create_task(
        api.client.post(
            song_url(pid), content=slow(), headers={**headers(), "content-length": str(len(WAV))}
        )
    )
    for _ in range(100):
        if await status_of(api, pid) == "uploading":
            break
        await asyncio.sleep(0.05)
    second = await api.client.post(song_url(pid), content=WAV, headers=headers())
    assert second.status_code == 409
    assert second.json()["error"]["details"]["reason"] == "upload_in_progress"
    release.set()
    assert (await first).status_code == 202


async def test_not_enough_disk_is_507(migrated_db: Db, blob_root: Path) -> None:
    async with build_api(migrated_db, blob_root, disk_low_watermark_gb=10**7) as env:
        pid = await make_project(env)
        r = await env.client.post(song_url(pid), content=WAV, headers=headers())
        assert r.status_code == 507
        assert r.json()["error"]["code"] == "insufficient_storage"
        assert await status_of(env, pid) == "created"


@pytest.mark.parametrize("status", ["rejected", "canceled"])
async def test_a_new_upload_is_accepted_from_rejected_and_canceled(
    api: ApiEnv, status: str
) -> None:
    pid = await make_project(api)
    await sql(api.db, "UPDATE projects SET status = $2 WHERE id = $1", UUID(pid), status)
    r = await api.client.post(song_url(pid), content=WAV, headers=headers())
    assert r.status_code == 202
    assert await status_of(api, pid) == "validating"


@pytest.mark.parametrize("status", ["validating", "analyzing", "draft_ready", "failed_analysis"])
async def test_other_states_refuse_an_upload(api: ApiEnv, status: str) -> None:
    pid = await make_project(api)
    await sql(api.db, "UPDATE projects SET status = $2 WHERE id = $1", UUID(pid), status)
    r = await api.client.post(song_url(pid), content=WAV, headers=headers())
    assert r.status_code == 409
    assert await status_of(api, pid) == status


async def test_a_stale_uploading_project_can_be_uploaded_again(api: ApiEnv) -> None:
    """The API died mid-upload: `uploading` for longer than the stale limit is abandoned."""
    pid = await make_project(api)
    await sql(
        api.db,
        "UPDATE projects SET status = 'uploading', updated_at = now() - interval '11 minutes'"
        " WHERE id = $1",
        UUID(pid),
    )
    r = await api.client.post(song_url(pid), content=WAV, headers=headers())
    assert r.status_code == 202, r.text
    assert await status_of(api, pid) == "validating"


async def test_a_fresh_uploading_project_still_refuses_a_second_upload(api: ApiEnv) -> None:
    pid = await make_project(api)
    await sql(
        api.db,
        "UPDATE projects SET status = 'uploading', updated_at = now() - interval '9 minutes'"
        " WHERE id = $1",
        UUID(pid),
    )
    r = await api.client.post(song_url(pid), content=WAV, headers=headers())
    assert r.status_code == 409
    assert await status_of(api, pid) == "uploading"


async def test_a_replacing_upload_resets_the_song_row(api: ApiEnv) -> None:
    pid = await make_project(api)
    await sql(api.db, "UPDATE projects SET status = 'rejected' WHERE id = $1", UUID(pid))
    await api.client.post(song_url(pid), content=WAV, headers=headers("one.wav"))
    await sql(
        api.db, "UPDATE songs SET codec = 'pcm', duration_s = 20 WHERE project_id = $1", UUID(pid)
    )
    await sql(api.db, "UPDATE projects SET status = 'canceled' WHERE id = $1", UUID(pid))
    again = await api.client.post(song_url(pid), content=MP3, headers=headers("two.mp3"))
    assert again.status_code == 202
    rows = await sql(
        api.db,
        "SELECT original_filename, codec, duration_s FROM songs WHERE project_id = $1",
        UUID(pid),
    )
    assert [tuple(r) for r in rows] == [("two.mp3", None, None)]


async def test_a_foreign_origin_is_refused_by_the_guard(api: ApiEnv) -> None:
    pid = await make_project(api)
    r = await api.client.post(
        song_url(pid), content=WAV, headers={**headers(), "origin": "http://evil.example"}
    )
    assert r.status_code == 403
    assert blob_files(api.blob_root) == []


async def test_another_users_project_is_a_404(api: ApiEnv) -> None:
    await sql(api.db, "INSERT INTO users (id, email) VALUES ($1, 'b@example.test')", OTHER)
    other_pid = UUID("00000000-0000-4000-8000-0000000000cc")
    await sql(api.db, "INSERT INTO projects (id, user_id) VALUES ($1, $2)", other_pid, OTHER)
    r = await api.client.post(song_url(str(other_pid)), content=WAV, headers=headers())
    assert r.status_code == 404
    assert blob_files(api.blob_root) == []
    assert (await sql(api.db, "SELECT status FROM projects WHERE id = $1", other_pid))[0][
        0
    ] == "created"
    assert (await api.client.get(f"/api/v1/projects/{other_pid}")).status_code == 404


def _slow_writer(monkeypatch: pytest.MonkeyPatch) -> None:
    """A writer that is slower than the network: the bounded queue must push back."""
    real = FilesystemBlobStore.put

    def slow_put(
        self: FilesystemBlobStore, key: str, stream: Iterable[bytes], *, max_bytes: int
    ) -> int:
        def slowed() -> Iterator[bytes]:
            for chunk in stream:
                time.sleep(0.01)
                yield chunk

        return real(self, key, slowed(), max_bytes=max_bytes)

    monkeypatch.setattr(FilesystemBlobStore, "put", slow_put)


async def _chunks(data: bytes, size: int = 64 * 1024) -> AsyncIterator[bytes]:
    for i in range(0, len(data), size):
        yield data[i : i + size]


async def test_a_slow_writer_pushes_back_and_every_byte_arrives(
    api: ApiEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    _slow_writer(monkeypatch)
    pid = await make_project(api)
    big = WAV + b"\x01" * (3 * 1024 * 1024)
    r = await api.client.post(
        song_url(pid),
        content=_chunks(big),
        headers={**headers(), "content-length": str(len(big))},
    )
    assert r.status_code == 202, r.text
    assert (api.blob_root / "songs" / pid / "incoming.bin").read_bytes() == big


async def test_exceeding_the_cap_mid_stream_stops_the_upload(
    api: ApiEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    _slow_writer(monkeypatch)
    pid = await make_project(api)
    big = WAV + b"\x01" * (3 * 1024 * 1024)
    r = await api.client.post(
        song_url(pid),
        content=_chunks(big),
        headers={**headers(), "content-length": str(512 * 1024)},  # the sender lies low
    )
    assert r.status_code == 413
    assert blob_files(api.blob_root) == []
    assert await status_of(api, pid) == "created"

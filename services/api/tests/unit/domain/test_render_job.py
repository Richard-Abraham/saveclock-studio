import hashlib

from saveclock.domain.render_job import RENDER_FILES, DownloadKind, job_hash


def test_the_job_hash_is_sha256_of_plan_hash_then_song_hash() -> None:
    plan, song = bytes(range(32)), bytes(range(32, 64))
    assert job_hash(plan, song) == hashlib.sha256(plan + song).digest()
    assert job_hash(plan, song) != job_hash(song, plan)


def test_the_download_kinds_are_exactly_the_file_map() -> None:
    assert {k.value for k in DownloadKind} == set(RENDER_FILES)
    assert RENDER_FILES["silent_video"] == "master.mp4"

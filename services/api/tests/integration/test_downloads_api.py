"""Endpoint #21 (`GET /renders/{id}/download`) and #16 (`GET /projects/{id}/credits`)."""

from pathlib import Path
from urllib.parse import quote
from uuid import UUID

import pytest

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.errors import NotFound
from saveclock.services.files import serve
from tests.integration.render_harness import Renders

pytestmark = [pytest.mark.integration, pytest.mark.ffmpeg]
PID = UUID("33333333-3333-4333-8333-333333333333")
FILES = {
    "silent_video": ("master.mp4", "video/mp4"),
    "cutlist_json": ("cutlist.json", "application/json"),
    "cutlist_csv": ("cutlist.csv", "text/csv; charset=utf-8"),
    "with_song": ("with_song.mp4", "video/mp4"),
}


async def ready_with_mode_a(renderer: Renders) -> tuple[UUID, UUID]:
    d = renderer.draft
    pid = await d.drafted()
    rid = await renderer.ready(pid)
    assert (await renderer.mode_a(rid)).status_code == 202
    await renderer.run_remux(await renderer.job_of(rid, "remux"))
    return pid, rid


async def test_each_kind_returns_its_bytes_and_content_type(renderer: Renders) -> None:
    _, rid = await ready_with_mode_a(renderer)
    for kind, (name, ctype) in FILES.items():
        r = await renderer.client.get(f"/api/v1/renders/{rid}/download", params={"kind": kind})
        assert r.status_code == 200, kind
        assert r.content == renderer.path(rid, name).read_bytes()
        assert r.headers["content-type"] == ctype
        assert r.headers["accept-ranges"] == "bytes"


async def test_the_download_headers_are_safe_and_the_name_comes_from_the_title(
    renderer: Renders,
) -> None:
    d = renderer.draft
    pid = await d.drafted()
    await d.sql("UPDATE projects SET title = $1 WHERE id = $2", "Café Dreams", pid)
    rid = await renderer.ready(pid)
    r = await renderer.client.get(
        f"/api/v1/renders/{rid}/download", params={"kind": "silent_video"}
    )
    disposition = r.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="Caf-Dreams-silent_video.mp4"')
    assert f"filename*=UTF-8''{quote('Café-Dreams-silent_video.mp4')}" in disposition
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "private, no-store"


async def test_a_title_less_project_is_named_from_the_render_id(renderer: Renders) -> None:
    d = renderer.draft
    pid = await d.drafted()
    await d.sql("UPDATE projects SET title = NULL WHERE id = $1", pid)
    rid = await renderer.ready(pid)
    r = await renderer.client.get(f"/api/v1/renders/{rid}/download", params={"kind": "cutlist_csv"})
    assert (
        f'filename="saveclock-{str(rid)[:8]}-cutlist_csv.csv"' in r.headers["content-disposition"]
    )


async def test_a_range_gives_206_with_content_range_and_a_repeat_works(renderer: Renders) -> None:
    d = renderer.draft
    rid = await renderer.ready(await d.drafted())
    url = f"/api/v1/renders/{rid}/download"
    size = renderer.path(rid, "master.mp4").stat().st_size
    whole = renderer.path(rid, "master.mp4").read_bytes()
    part = await renderer.client.get(
        url, params={"kind": "silent_video"}, headers={"range": "bytes=0-99"}
    )
    assert part.status_code == 206
    assert part.headers["content-range"] == f"bytes 0-99/{size}"
    assert part.content == whole[:100]
    for _ in range(2):  # downloading twice works
        again = await renderer.client.get(url, params={"kind": "silent_video"})
        assert again.content == whole


async def test_every_kind_is_409_until_the_render_is_ready(renderer: Renders) -> None:
    rid, _ = await renderer.start(await renderer.draft.drafted())
    for kind in FILES:
        r = await renderer.client.get(f"/api/v1/renders/{rid}/download", params={"kind": kind})
        assert (r.status_code, r.json()["error"]["details"]["reason"]) == (409, "not_ready")


async def test_with_song_is_409_until_mode_a_is_ready(renderer: Renders) -> None:
    rid = await renderer.ready(await renderer.draft.drafted())
    url = f"/api/v1/renders/{rid}/download"
    assert (await renderer.client.get(url, params={"kind": "silent_video"})).status_code == 200
    assert (await renderer.client.get(url, params={"kind": "with_song"})).status_code == 409
    await renderer.mode_a(rid)  # queued is not ready either
    assert (await renderer.client.get(url, params={"kind": "with_song"})).status_code == 409


async def test_an_unknown_or_path_like_kind_is_422_and_never_reaches_a_key(
    renderer: Renders,
) -> None:
    rid = await renderer.ready(await renderer.draft.drafted())
    url = f"/api/v1/renders/{rid}/download"
    for kind in ("nope", "../..", "../../songs/x/source.mp3", "master.mp4", ""):
        r = await renderer.client.get(url, params={"kind": kind})
        assert r.status_code == 422, kind
    assert (await renderer.client.get(url)).status_code == 422  # no kind at all


async def test_the_credits_list_the_working_plan_and_a_ready_to_copy_text(
    renderer: Renders,
) -> None:
    d = renderer.draft
    pid = await d.drafted()
    r = await renderer.client.get(f"/api/v1/projects/{pid}/credits")
    assert r.status_code == 200
    body = r.json()
    plan = await d.plan(pid)
    assert sum(i["uses"] for i in body["items"]) == len(plan.cuts)
    assert body["text"].splitlines()[0].startswith("Footage: Fake Author on Pexels - https://")
    assert len(body["text"].splitlines()) == len(body["items"])
    fresh = (await d.client.post("/api/v1/projects", json={})).json()["id"]
    none = await renderer.client.get(f"/api/v1/projects/{fresh}/credits")
    assert (none.status_code, none.json()["error"]["details"]["reason"]) == (409, "no_plan_yet")


# --- what serve() may and may not reach (the blob directory is never a download) ---------------


@pytest.mark.parametrize(
    "key",
    [
        f"songs/{PID}/source.mp3",
        f"work/{PID}/canonical.flac",
        f"work/{PID}/raw/pexels_1.mp4",
        f"work/{PID}/mezz/pexels_1.mp4",
        f"work/{PID}/emb/pexels_1.npy",
        "renders/../songs/x/source.mp3",
        f"renders/{PID}/master.mp4.part",
    ],
)
def test_serve_refuses_every_intermediate_and_the_original_song(tmp_path: Path, key: str) -> None:
    store = FilesystemBlobStore(str(tmp_path), 0)
    with pytest.raises(NotFound):
        serve(store, key, None)


def test_serve_does_reach_the_render_files_and_proxies(tmp_path: Path) -> None:
    # `is_servable` also allows the preview proxies: say so here
    store = FilesystemBlobStore(str(tmp_path), 0)
    for key in (
        f"renders/{PID}/master.mp4",
        f"renders/{PID}/cutlist.json",
        f"renders/{PID}/cutlist.csv",
        f"renders/{PID}/with_song.mp4",
        f"work/{PID}/proxy/a.mp4",
        f"work/{PID}/audio_proxy.m4a",
    ):
        store.put(key, iter([b"x"]), max_bytes=10)
        assert b"".join(serve(store, key, None).body) == b"x"

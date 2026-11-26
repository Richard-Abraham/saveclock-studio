"""Endpoints #17 to #19 and #22 over the real app and Postgres (the worker is bypassed)."""

import asyncio
import json
from uuid import UUID

import pytest

from tests.integration.conftest import build_api
from tests.integration.draft_harness import Draft
from tests.integration.render_harness import Renders

pytestmark = [pytest.mark.integration, pytest.mark.ffmpeg]
OTHER = UUID("00000000-0000-4000-8000-0000000000bb")


async def count(draft: Draft, query: str, *args: object) -> int:
    return int((await draft.sql(query, *args))[0][0])


async def test_a_render_is_accepted_queued_and_enqueued_by_ids_only(renderer: Renders) -> None:
    d = renderer.draft
    pid = await d.drafted()
    r = await renderer.post(pid)
    assert r.status_code == 202
    rid = UUID(r.json()["render_id"])
    assert await d.status(pid) == ("rendering", None)
    job = await renderer.job_of(rid, "render")
    assert renderer.api_sent[-1] == (
        "render_master",
        (str(job), "00000000-0000-4000-8000-000000000001"),
    )
    got = (await renderer.client.get(f"/api/v1/renders/{rid}")).json()
    assert (got["state"], got["plan_version"], got["queue_position"]) == ("queued", 1, 1)
    assert got["files"] == []
    assert (got["mode_a_state"], got["verify"]) == (None, None)


async def test_the_plan_is_frozen_and_a_later_edit_makes_the_next_version(
    renderer: Renders,
) -> None:
    d = renderer.draft
    pid = await d.drafted()
    rid = await renderer.ready(pid)
    assert (await d.sql("SELECT frozen_at IS NOT NULL FROM edit_plans WHERE version = 1"))[0][0]
    patched = await d.client.patch(
        f"/api/v1/projects/{pid}/plan",
        json={"base_version": 1, "ops": [{"op": "set_density", "level": 1}]},
    )
    assert patched.status_code == 200
    assert patched.json()["version"] == 2
    again = (await renderer.post(pid)).json()["render_id"]  # a changed plan: a new render
    assert again != str(rid)


async def test_an_identical_second_post_returns_the_same_render_and_makes_no_job(
    renderer: Renders,
) -> None:
    d = renderer.draft
    pid = await d.drafted()
    first = await renderer.post(pid)
    second = await renderer.post(pid)  # while it is queued, the project is `rendering`
    assert (first.status_code, second.status_code) == (202, 202)
    assert second.json() == first.json()
    assert await count(d, "SELECT count(*) FROM renders") == 1
    assert await count(d, "SELECT count(*) FROM jobs WHERE stage = 'render'") == 1
    assert [a for a, _ in renderer.api_sent].count("render_master") == 1


async def test_a_ready_render_is_returned_for_the_same_plan(renderer: Renders) -> None:
    d = renderer.draft
    pid = await d.drafted()
    rid = await renderer.ready(pid)
    again = await renderer.post(pid)
    assert again.status_code == 202
    assert again.json()["render_id"] == str(rid)
    assert await count(d, "SELECT count(*) FROM renders") == 1
    assert await d.status(pid) == ("ready", None)  # nothing moved


async def test_a_failed_render_allows_the_same_plan_again(renderer: Renders) -> None:
    d = renderer.draft
    pid = await d.drafted()
    rid, _ = await renderer.start(pid)
    await d.sql(
        "UPDATE renders SET state = 'failed', error_code = 'internal_error' WHERE id = $1", rid
    )
    await d.sql("UPDATE projects SET status = 'failed_render' WHERE id = $1", pid)
    again = await renderer.post(pid)
    assert again.status_code == 202
    assert again.json()["render_id"] != str(rid)
    assert await d.status(pid) == ("rendering", None)


async def test_a_project_that_is_not_ready_to_render_is_409(renderer: Renders) -> None:
    d = renderer.draft
    pid = await d.drafted()
    await d.sql("UPDATE projects SET status = 'planning' WHERE id = $1", pid)
    r = await renderer.post(pid)
    assert (r.status_code, r.json()["error"]["details"]["reason"]) == (409, "wrong_state")
    fresh = (await d.client.post("/api/v1/projects", json={})).json()["id"]
    none = await renderer.post(UUID(fresh))
    assert (none.status_code, none.json()["error"]["details"]["reason"]) == (409, "no_plan_yet")
    assert await count(d, "SELECT count(*) FROM renders") == 0


async def test_an_unknown_plan_version_is_404(renderer: Renders) -> None:
    pid = await renderer.draft.drafted()
    assert (await renderer.post(pid, {"plan_version": 9})).status_code == 404
    assert (await renderer.post(pid, {"plan_version": 0})).status_code == 422
    assert await count(renderer.draft, "SELECT count(*) FROM renders") == 0


async def test_low_disk_is_507_and_nothing_is_created(renderer: Renders) -> None:
    d = renderer.draft
    pid = await d.drafted()
    async with build_api(d.env.db, d.env.blob_root, disk_low_watermark_gb=10**9) as full:
        r = await full.client.post(f"/api/v1/projects/{pid}/renders", json={})
    assert (r.status_code, r.json()["error"]["code"]) == (507, "insufficient_storage")
    assert await count(d, "SELECT count(*) FROM renders") == 0
    assert await d.status(pid) == ("draft_ready", None)


async def test_a_missing_mezzanine_is_409_intermediates_missing(renderer: Renders) -> None:
    d = renderer.draft
    pid = await d.drafted()
    plan = await d.plan(pid)
    (d.env.blob_root / plan.cuts[0].clip.mezzanine_key).unlink()
    r = await renderer.post(pid)
    assert (r.status_code, r.json()["error"]["details"]["reason"]) == (409, "intermediates_missing")
    assert await d.status(pid) == ("draft_ready", None)
    assert await count(d, "SELECT count(*) FROM renders") == 0


async def test_a_render_job_already_active_is_409_job_active(renderer: Renders) -> None:
    d = renderer.draft
    pid = await d.drafted()
    await d.sql(
        "INSERT INTO jobs (id, project_id, stage, queue, state) "
        "VALUES (gen_random_uuid(), $1, 'remux', 'render', 'queued')",
        pid,
    )
    r = await renderer.post(pid)
    assert (r.status_code, r.json()["error"]["details"]["reason"]) == (409, "job_active")
    assert await d.status(pid) == ("draft_ready", None)  # rolled back whole
    assert await count(d, "SELECT count(*) FROM renders") == 0


async def test_a_foreign_origin_is_refused(renderer: Renders) -> None:
    pid = await renderer.draft.drafted()
    r = await renderer.client.post(
        f"/api/v1/projects/{pid}/renders", json={}, headers={"origin": "http://evil.example"}
    )
    assert r.status_code == 403


async def test_another_users_render_is_404_on_every_endpoint(renderer: Renders) -> None:
    d = renderer.draft
    pid = await d.drafted()
    rid = await renderer.ready(pid)
    await d.sql("INSERT INTO users (id, email) VALUES ($1, 'b@example.test')", OTHER)
    await d.sql("UPDATE projects SET user_id = $1 WHERE id = $2", OTHER, pid)
    await d.sql("UPDATE renders SET user_id = $1 WHERE id = $2", OTHER, rid)
    c, base = renderer.client, f"/api/v1/renders/{rid}"
    assert (await c.get(base)).status_code == 404
    assert (await c.post(f"{base}/cancel")).status_code == 404
    assert (await c.post(f"{base}/mode-a")).status_code == 404
    assert (await c.get(f"{base}/download", params={"kind": "silent_video"})).status_code == 404
    assert (await c.delete(base)).status_code == 404
    assert (await renderer.post(pid)).status_code == 404
    assert (await c.get(f"/api/v1/projects/{pid}/credits")).status_code == 404


async def test_cancel_a_queued_render_ends_it_and_gives_the_plan_back(renderer: Renders) -> None:
    d = renderer.draft
    pid = await d.drafted()
    rid, job = await renderer.start(pid)
    r = await renderer.client.post(f"/api/v1/renders/{rid}/cancel")
    assert r.status_code == 202
    assert r.json()["state"] == "canceled"
    assert await d.status(pid) == ("draft_ready", None)
    assert await d.job(job) == ("error", "canceled")
    await renderer.run_render(job)  # the worker finds nothing to do
    assert (await renderer.render_row(rid))["state"] == "canceled"
    assert (await renderer.client.post(f"/api/v1/renders/{rid}/cancel")).status_code == 409


async def test_cancel_a_running_render_only_flags_the_job(renderer: Renders) -> None:
    d = renderer.draft
    pid = await d.drafted()
    rid, job = await renderer.start(pid)
    await d.sql("UPDATE renders SET state = 'running' WHERE id = $1", rid)
    await d.sql("UPDATE jobs SET state = 'running' WHERE id = $1", job)
    r = await renderer.client.post(f"/api/v1/renders/{rid}/cancel")
    assert (r.status_code, r.json()["state"]) == (202, "running")  # the worker ends it
    assert (await d.sql("SELECT cancel_requested FROM jobs WHERE id = $1", job))[0][0]
    assert await d.status(pid) == ("rendering", None)


async def test_delete_is_refused_while_running_and_removes_a_finished_render(
    renderer: Renders,
) -> None:
    d = renderer.draft
    pid = await d.drafted()
    rid, job = await renderer.start(pid)
    busy = await renderer.client.delete(f"/api/v1/renders/{rid}")
    assert (busy.status_code, busy.json()["error"]["details"]["reason"]) == (409, "wrong_state")
    await renderer.run_render(job)
    assert renderer.path(rid, "master.mp4").is_file()
    done = await renderer.client.delete(f"/api/v1/renders/{rid}")
    assert done.status_code == 204
    assert not (d.env.blob_root / "renders" / str(rid)).exists()
    assert await count(d, "SELECT count(*) FROM renders") == 0
    assert (await d.sql("SELECT render_id FROM jobs WHERE id = $1", job))[0][0] is None
    assert await d.status(pid) == ("draft_ready", None)  # the only ready render went away


async def test_the_project_detail_carries_the_latest_render(renderer: Renders) -> None:
    d = renderer.draft
    pid = await d.drafted()
    assert (await d.client.get(f"/api/v1/projects/{pid}")).json()["render"] is None
    rid = await renderer.ready(pid)
    detail = (await d.client.get(f"/api/v1/projects/{pid}")).json()
    assert detail["render"] == {"id": str(rid), "state": "ready", "mode_a_state": None}


async def test_a_ready_render_reports_its_checks_and_files(renderer: Renders) -> None:
    d = renderer.draft
    pid = await d.drafted()
    rid = await renderer.ready(pid)
    got = (await renderer.client.get(f"/api/v1/renders/{rid}")).json()
    assert got["state"] == "ready"
    assert got["files"] == ["silent_video", "cutlist_json", "cutlist_csv"]
    assert got["verify"]["passed"] is True
    assert got["verify"]["blocks"] == 0
    assert got["verify"]["max_cut_error_frames"] == 0
    assert got["verify"]["duration_delta_frames"] == 0
    assert got["verify"]["attribution_present"] is True
    plan = await d.plan(pid)
    assert got["duration_frames"] == plan.total_frames
    assert got["size_bytes"] == renderer.path(rid, "master.mp4").stat().st_size
    assert await d.status(pid) == ("ready", None)
    kinds = d.recorder.kinds()
    assert "render_ready" in kinds
    assert kinds.index("render_ready") > kinds.index("progress")


async def test_the_cut_lists_are_published_with_the_master(renderer: Renders) -> None:
    d = renderer.draft
    pid = await d.drafted()
    rid = await renderer.ready(pid)
    plan = await d.plan(pid)
    doc = json.loads(await asyncio.to_thread(renderer.path(rid, "cutlist.json").read_text))
    assert [c["start_frame"] for c in doc["cuts"]] == [c.out_start_frame for c in plan.cuts]
    assert doc["total_frames"] == plan.total_frames
    assert renderer.path(rid, "cutlist.csv").read_text().count("\r\n") == len(plan.cuts) + 1

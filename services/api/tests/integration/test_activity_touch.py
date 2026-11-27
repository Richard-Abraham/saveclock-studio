"""Which routes count as activity for the retention clock (plan 008, P8-13).

A project's intermediates are swept 7 days after `last_activity_at`. Reading or editing a project
must move it; a refused call must not; every status change moves it. The inventory is keyed by
`operation_id` and fails naming any route with a project or render id that is in neither table.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from saveclock.repositories.projects import ProjectRepository
from saveclock.services.identity import OWNER_USER_ID
from tests.integration.draft_harness import Draft
from tests.integration.test_sse import Live
from tests.unit.test_conventions import v1_routes

pytestmark = pytest.mark.integration

# a successful call moves `last_activity_at`
BUMP = frozenset(
    {
        "get_project",
        "get_analysis",
        "get_plan",
        "patch_plan",
        "get_credits",
        "stream_events",
        "get_render",
        "download_render",
        "create_render",
        "request_mode_a",
    }
)
# moves it only through a status change it causes
STATUS_ONLY = frozenset(
    {
        "patch_project",
        "cancel_project",
        "retry_project",
        "cancel_render",
        "delete_render",
        "upload_song",
        "delete_project",
    }
)
ID_PARAMS = {"project_id", "render_id"}


@pytest.mark.unit
def test_every_route_with_a_project_or_render_id_is_in_one_table() -> None:
    uncategorised = sorted(
        r.operation_id or r.path
        for r in v1_routes()
        if ID_PARAMS & {p.name for p in r.dependant.path_params}
        and (r.operation_id not in BUMP | STATUS_ONLY)
    )
    assert uncategorised == [], f"add these routes to BUMP or STATUS_ONLY: {uncategorised}"
    names = {r.operation_id for r in v1_routes()}
    assert names >= (BUMP | STATUS_ONLY), "a table row names a route that no longer exists"


async def activity(d: Draft, pid: UUID) -> datetime:
    row = await d.sql("SELECT last_activity_at FROM projects WHERE id=$1", pid)
    stamp: datetime = row[0][0]
    return stamp


async def age(d: Draft, pid: UUID) -> datetime:
    await d.sql("UPDATE projects SET last_activity_at = now() - interval '8 days' WHERE id=$1", pid)
    return await activity(d, pid)


async def test_reads_and_edits_move_the_clock_and_the_table_is_complete(draft: Draft) -> None:
    pid = await draft.drafted()
    version = (await draft.client.get(f"/api/v1/projects/{pid}/plan")).json()["version"]
    calls = {
        "get_project": ("GET", f"/api/v1/projects/{pid}", None),
        "get_analysis": ("GET", f"/api/v1/projects/{pid}/analysis", None),
        "get_plan": ("GET", f"/api/v1/projects/{pid}/plan", None),
        "get_credits": ("GET", f"/api/v1/projects/{pid}/credits", None),
        "patch_plan": (
            "PATCH",
            f"/api/v1/projects/{pid}/plan",
            {"base_version": version, "ops": [{"op": "lock_clip", "cut_index": 0, "locked": True}]},
        ),
    }
    for operation_id, (method, url, body) in calls.items():
        before = await age(draft, pid)
        response = await draft.client.request(method, url, json=body)
        assert response.status_code == 200, (operation_id, response.text)
        assert await activity(draft, pid) > before + timedelta(days=7), operation_id


async def test_watching_the_event_stream_counts(draft: Draft) -> None:
    """ASGITransport buffers a whole stream, so this one runs through a real uvicorn."""
    pid = await draft.drafted()
    before = await age(draft, pid)
    server = Live(draft.env.db, draft.env.blob_root, max_age_s=2.0)
    server.start()
    try:
        async with (
            server.client() as client,
            client.stream("GET", f"/api/v1/projects/{pid}/events") as response,
        ):
            assert response.status_code == 200
            async for _line in response.aiter_lines():
                break  # the first frame is out: the snapshot (and the touch) are done
    finally:
        server.stop()
    assert await activity(draft, pid) > before + timedelta(days=7)


async def test_render_routes_move_the_clock(draft: Draft) -> None:
    pid = await draft.drafted()
    before = await age(draft, pid)
    created = await draft.client.post(f"/api/v1/projects/{pid}/renders", json={})
    assert created.status_code == 202, created.text
    assert await activity(draft, pid) > before + timedelta(days=7)  # also a status change
    rid = created.json()["render_id"]

    before = await age(draft, pid)
    assert (await draft.client.get(f"/api/v1/renders/{rid}")).status_code == 200
    assert await activity(draft, pid) > before + timedelta(days=7), "get_render"

    await draft.sql("UPDATE renders SET state='ready' WHERE id=$1", UUID(rid))
    await draft.sql("UPDATE jobs SET state='ok', finished_at=now() WHERE render_id=$1", UUID(rid))
    draft.env.blob_root.joinpath("renders", rid).mkdir(parents=True)
    draft.env.blob_root.joinpath("renders", rid, "master.mp4").write_bytes(b"0" * 64)
    before = await age(draft, pid)
    got = await draft.client.get(f"/api/v1/renders/{rid}/download", params={"kind": "silent_video"})
    assert got.status_code == 200
    assert await activity(draft, pid) > before + timedelta(days=7), "download_render"

    before = await age(draft, pid)
    assert (await draft.client.post(f"/api/v1/renders/{rid}/mode-a")).status_code == 202
    assert await activity(draft, pid) > before + timedelta(days=7), "request_mode_a"


async def test_a_refused_call_does_not_move_the_clock(draft: Draft) -> None:
    pid = await draft.drafted()
    before = await age(draft, pid)
    stale = await draft.client.patch(
        f"/api/v1/projects/{pid}/plan",
        json={
            "base_version": 99,
            "ops": [{"op": "lock_clip", "cut_index": 0, "locked": True}],
        },
    )
    assert stale.status_code == 409
    refused_cancel = await draft.client.post(f"/api/v1/projects/{pid}/cancel")
    assert refused_cancel.status_code == 409  # a draft_ready project has nothing to cancel
    assert await activity(draft, pid) == before


async def test_a_status_change_moves_the_clock(draft: Draft) -> None:
    pid = await draft.drafted()
    before = await age(draft, pid)
    async with draft.ctx.sessionmaker() as session:
        moved = await ProjectRepository(session).transition(
            user_id=OWNER_USER_ID, project_id=pid, from_="draft_ready", to="planning"
        )
        await session.commit()
    assert moved
    assert await activity(draft, pid) > before + timedelta(days=7)
    assert datetime.now(UTC) - await activity(draft, pid) < timedelta(minutes=5)

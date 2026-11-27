"""`POST /housekeeping/run` (plan 008, #23): scopes, the lock, ownership, validation."""

from uuid import UUID

import httpx
import pytest

from saveclock.services.housekeeping import LOCK_KEY
from tests.integration.conftest import ApiEnv, Harness, insert_project, insert_user
from tests.integration.housekeeping_harness import NOW, Hk
from tests.integration.test_maintenance_worker import eventually

pytestmark = pytest.mark.integration
OTHER = UUID("00000000-0000-4000-8000-0000000000bb")
RUN = "/api/v1/housekeeping/run"


async def test_each_scope_sends_its_actors_with_ids_and_literals_only(hk: Hk, api: ApiEnv) -> None:
    user = str(hk.user)
    for scope, expected in (
        ("intermediates", [("sweep_intermediates", (user, ""))]),
        ("abandoned_uploads", [("reap_orphans", (user, "uploads"))]),
        ("all", [("sweep_intermediates", (user, "")), ("reap_orphans", (user, "uploads"))]),
    ):
        api.enqueuer.sent.clear()
        response = await api.client.post(RUN, json={"scope": scope})
        assert response.status_code == 202, response.text
        assert response.json() == {"scope": scope, "project_id": None}
        assert api.enqueuer.sent == expected


async def test_a_held_lock_is_409(hk: Hk, api: ApiEnv) -> None:
    hk.redis.set(LOCK_KEY, "sweep_intermediates", ex=60)
    response = await api.client.post(RUN, json={"scope": "all"})
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "job_active"
    assert api.enqueuer.sent == []


async def test_a_foreign_project_is_404_and_a_bad_scope_is_422(hk: Hk, api: ApiEnv) -> None:
    await insert_user(api.db, OTHER, "b@example.test")
    theirs = await insert_project(api.db, OTHER, "theirs", NOW)
    r = await api.client.post(RUN, json={"scope": "intermediates", "project_id": str(theirs)})
    assert r.status_code == 404
    assert (await api.client.post(RUN, json={"scope": "everything"})).status_code == 422
    assert (await api.client.post(RUN, json={})).status_code == 422
    mine = await hk.project()
    r = await api.client.post(RUN, json={"scope": "all", "project_id": str(mine)})
    assert r.status_code == 422  # a project id only makes sense with `intermediates`
    assert api.enqueuer.sent == []


async def test_a_project_with_a_running_job_is_409(hk: Hk, api: ApiEnv) -> None:
    pid = await hk.project(status="planning")
    await hk.job(pid, stage="draft", state="running")
    r = await api.client.post(RUN, json={"scope": "intermediates", "project_id": str(pid)})
    assert r.status_code == 409
    assert api.enqueuer.sent == []


async def test_intermediates_with_a_project_id_frees_that_project_now(
    hk: Hk, harness: Harness, api_client: httpx.AsyncClient
) -> None:
    fresh = await hk.project()  # active a moment ago: only the explicit request frees it
    other = await hk.project()
    harness.start_worker(["maintenance"])
    r = await api_client.post(RUN, json={"scope": "intermediates", "project_id": str(fresh)})
    assert r.status_code == 202, r.text
    await eventually(lambda: not hk.has(f"work/{fresh}"))
    assert hk.has(f"songs/{fresh}")
    assert len(hk.blobs.list(f"work/{other}")) == 4  # the other project is untouched

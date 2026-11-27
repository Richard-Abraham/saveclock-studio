"""`DELETE /projects/{id}` (plan 008, #5): hidden at once, every file and row gone in minutes."""

from datetime import timedelta
from uuid import UUID

import httpx
import pytest

from saveclock.services import housekeeping as hkp
from tests.integration.conftest import ApiEnv, Harness, insert_project, insert_user
from tests.integration.housekeeping_harness import NOW, Hk
from tests.integration.test_maintenance_worker import eventually

pytestmark = pytest.mark.integration
OTHER = UUID("00000000-0000-4000-8000-0000000000bb")
UNKNOWN = UUID("00000000-0000-4000-8000-00000000cafe")


async def project_rows(hk: Hk, pid: UUID) -> dict[str, int]:
    """Row counts of the project in every table that names it (the cascade, proven by SQL)."""
    tables = await hk.sql(
        "SELECT table_name FROM information_schema.columns"
        " WHERE table_schema='public' AND column_name='project_id'"
    )
    counts = {"projects": (await hk.sql("SELECT count(*) FROM projects WHERE id=$1", pid))[0][0]}
    for (table,) in tables:
        query = f"SELECT count(*) FROM {table} WHERE project_id=$1"  # noqa: S608 - catalogue names
        counts[table] = (await hk.sql(query, pid))[0][0]
    return counts


async def test_a_full_project_is_deleted_everywhere(
    hk: Hk, harness: Harness, api_client: httpx.AsyncClient
) -> None:
    pid = await hk.project(status="ready")
    plan = await hk.plan(pid)
    rid = await hk.render(pid, plan, mode_a=True)
    await hk.job(pid, stage="draft", state="ok", finished_age=timedelta(0))
    assert (await project_rows(hk, pid))["jobs"] == 1
    assert (await project_rows(hk, pid))["renders"] == 1
    harness.start_worker(["maintenance"])

    response = await api_client.delete(f"/api/v1/projects/{pid}")
    assert response.status_code == 202, response.text
    assert response.json() == {"project_id": str(pid)}
    listed = (await api_client.get("/api/v1/projects")).json()["items"]
    assert str(pid) not in [i["id"] for i in listed]  # hidden at once, before any purge

    async def gone() -> bool:
        return not any((await project_rows(hk, pid)).values())

    await eventually(gone)
    for prefix in (f"songs/{pid}", f"work/{pid}", f"renders/{rid}"):
        assert hk.blobs.list(prefix) == []
    assert await project_rows(hk, pid) == dict.fromkeys(await project_rows(hk, pid), 0)


async def test_a_second_delete_and_a_foreign_project_are_404(hk: Hk, api: ApiEnv) -> None:
    mine = await hk.project()
    await insert_user(api.db, OTHER, "b@example.test")
    theirs = await insert_project(api.db, OTHER, "theirs", NOW)
    assert (await api.client.delete(f"/api/v1/projects/{theirs}")).status_code == 404
    assert (await api.client.delete(f"/api/v1/projects/{mine}")).status_code == 202
    assert (await api.client.delete(f"/api/v1/projects/{mine}")).status_code == 404
    assert (await api.client.delete(f"/api/v1/projects/{UNKNOWN}")).status_code == 404
    assert [a for a, _ in api.enqueuer.sent] == ["purge_project"]  # once, for mine only


async def test_deleting_while_a_job_runs_cancels_it_and_the_purge_waits(
    hk: Hk, api: ApiEnv
) -> None:
    pid = await hk.project(status="rendering")
    plan = await hk.plan(pid)
    rid = await hk.render(pid, plan)
    await hk.sql("UPDATE renders SET state='running' WHERE id=$1", rid)
    job = await hk.job(pid, stage="render", state="running")

    assert (await api.client.delete(f"/api/v1/projects/{pid}")).status_code == 202

    row = (await hk.sql("SELECT cancel_requested FROM jobs WHERE id=$1", job))[0]
    assert row[0] is True  # the running worker will see it between sub-steps
    assert (await hk.sql("SELECT status FROM projects WHERE id=$1", pid))[0][0] == "deleted"
    with pytest.raises(hkp.PurgeBusy):
        await hkp.purge_project(hk.ctx, hk.user, pid)
    assert hk.has(f"renders/{rid}")  # nothing was deleted under a running job
    await hk.sql("UPDATE jobs SET state='error', finished_at=now() WHERE id=$1", job)
    await hkp.purge_project(hk.ctx, hk.user, pid)
    assert not hk.has(f"renders/{rid}")
    assert not any((await project_rows(hk, pid)).values())


async def test_a_queued_render_is_canceled_by_the_delete(hk: Hk, api: ApiEnv) -> None:
    pid = await hk.project(status="rendering")
    rid = await hk.render(pid, await hk.plan(pid))
    await hk.sql("UPDATE renders SET state='queued' WHERE id=$1", rid)
    await hk.job(pid, stage="render", state="queued")
    assert (await api.client.delete(f"/api/v1/projects/{pid}")).status_code == 202
    assert (await hk.sql("SELECT state FROM renders WHERE id=$1", rid))[0][0] == "canceled"
    assert (await hk.sql("SELECT error_code FROM jobs WHERE project_id=$1", pid))[0][
        0
    ] == "canceled"


async def test_a_project_stuck_in_deleted_is_cleaned_by_the_next_sweep(hk: Hk) -> None:
    """A crash between the status change and the purge leaves the blobs: the sweeper retries."""
    pid = await hk.project(status="deleted")
    rid = await hk.render(pid, await hk.plan(pid))
    report = await hkp.sweep_intermediates(hk.ctx, hk.user)
    assert report.purged == [pid]
    for prefix in (f"songs/{pid}", f"work/{pid}", f"renders/{rid}"):
        assert not hk.has(prefix)
    assert not any((await project_rows(hk, pid)).values())

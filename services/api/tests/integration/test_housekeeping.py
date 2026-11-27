"""Retention and housekeeping against a real database and a real blob root (plan 008, Step 2).

Time is an injected clock (`NOW`) and SQL timestamps; no test sleeps. Every deletion test has its
negative twin: what must NOT be deleted is compared byte for byte afterwards.
"""

import os
import time
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import pytest

from saveclock.config import STUCK_QUEUED_S
from saveclock.ids import new_id
from saveclock.repositories.projects import ProjectRepository
from saveclock.services import housekeeping as hkp
from saveclock.services.context import WorkerContext
from saveclock.services.housekeeping import MAX_RESENDS, PurgeBusy
from tests.integration.conftest import insert_user
from tests.integration.housekeeping_harness import DAY, NOW, Hk, clock

pytestmark = pytest.mark.integration

TTL = timedelta(days=7)


def snapshot(hk: Hk, *prefixes: str) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for prefix in prefixes:
        for key in hk.blobs.list(prefix):
            out[key] = b"".join(hk.blobs.open(key))
    return out


async def test_an_idle_project_loses_its_intermediates_and_nothing_else(hk: Hk) -> None:
    pid = await hk.project(idle=8 * DAY)
    plan = await hk.plan(pid)
    rid = await hk.render(pid, plan, mode_a=True)
    keep = snapshot(hk, f"songs/{pid}", f"renders/{rid}")
    assert len(keep) == 3  # source, master, with_song

    report = await hkp.sweep_intermediates(hk.ctx, hk.user, clock=clock)

    assert report.projects == [pid]
    assert report.freed_bytes == 400  # four intermediates of 100 bytes
    assert not hk.has(f"work/{pid}")
    assert (await hk.sql("SELECT intermediates_purged_at FROM projects WHERE id=$1", pid))[0][0]
    assert snapshot(hk, f"songs/{pid}", f"renders/{rid}") == keep  # byte-identical
    assert (await hk.sql("SELECT count(*) FROM edit_plans WHERE project_id=$1", pid))[0][0] == 1
    assert (await hk.sql("SELECT count(*) FROM renders WHERE project_id=$1", pid))[0][0] == 1


async def test_the_ttl_boundary_is_strict(hk: Hk) -> None:
    exactly = await hk.project(idle=TTL)
    minute_short = await hk.project(idle=TTL - timedelta(minutes=1))
    minute_over = await hk.project(idle=TTL + timedelta(minutes=1))
    report = await hkp.sweep_intermediates(hk.ctx, hk.user, clock=clock)
    assert report.projects == [minute_over]
    assert hk.has(f"work/{exactly}")
    assert hk.has(f"work/{minute_short}")
    assert not hk.has(f"work/{minute_over}")


@pytest.mark.parametrize("state", ["queued", "running"])
async def test_a_project_with_an_active_job_is_untouched(hk: Hk, state: str) -> None:
    pid = await hk.project(idle=30 * DAY, status="planning")
    await hk.job(pid, stage="draft", state=state)
    report = await hkp.sweep_intermediates(hk.ctx, hk.user, clock=clock)
    assert report.projects == []
    assert len(hk.blobs.list(f"work/{pid}")) == 4


async def test_a_finished_job_does_not_protect_a_project(hk: Hk) -> None:
    pid = await hk.project(idle=30 * DAY)
    await hk.job(pid, stage="draft", state="ok", finished_age=29 * DAY)
    assert (await hkp.sweep_intermediates(hk.ctx, hk.user, clock=clock)).projects == [pid]


async def test_a_purged_project_is_not_swept_again(hk: Hk) -> None:
    pid = await hk.project(idle=30 * DAY, purged=True)
    assert (await hkp.sweep_intermediates(hk.ctx, hk.user, clock=clock)).projects == []
    assert len(hk.blobs.list(f"work/{pid}")) == 4


async def test_a_deleted_project_is_purged_not_swept(hk: Hk) -> None:
    pid = await hk.project(status="deleted", idle=30 * DAY)
    plan = await hk.plan(pid)
    rid = await hk.render(pid, plan, mode_a=True)
    report = await hkp.sweep_intermediates(hk.ctx, hk.user, clock=clock)
    assert report.projects == []
    assert report.purged == [pid]
    for prefix in (f"songs/{pid}", f"work/{pid}", f"renders/{rid}"):
        assert not hk.has(prefix)
    assert (await hk.sql("SELECT count(*) FROM projects WHERE id=$1", pid))[0][0] == 0
    assert (await hk.sql("SELECT count(*) FROM renders WHERE id=$1", rid))[0][0] == 0


async def test_the_sweep_is_idempotent(hk: Hk) -> None:
    await hk.project(idle=9 * DAY)
    first = await hkp.sweep_intermediates(hk.ctx, hk.user, clock=clock)
    second = await hkp.sweep_intermediates(hk.ctx, hk.user, clock=clock)
    assert first.freed_bytes == 400
    assert second.freed_bytes == 0
    assert second.projects == []


async def test_dry_run_reports_the_same_numbers_and_deletes_nothing(hk: Hk) -> None:
    pid = await hk.project(idle=9 * DAY)
    gone = await hk.project(status="deleted")
    before = snapshot(hk, "songs", "work")
    dry = await hkp.sweep_intermediates(hk.ctx, hk.user, dry_run=True, clock=clock)
    assert snapshot(hk, "songs", "work") == before
    assert (await hk.sql("SELECT intermediates_purged_at FROM projects WHERE id=$1", pid))[0][
        0
    ] is None
    assert (await hk.sql("SELECT count(*) FROM projects WHERE id=$1", gone))[0][0] == 1
    real = await hkp.sweep_intermediates(hk.ctx, hk.user, clock=clock)
    assert (dry.freed_bytes, dry.projects) == (real.freed_bytes, real.projects) == (400, [pid])
    assert dry.dry_run is True


async def test_a_second_user_cannot_have_the_owners_projects_swept(hk: Hk) -> None:
    other = UUID("00000000-0000-4000-8000-0000000000bb")
    await insert_user(hk.db, other, "b@example.test")
    mine = await hk.project(idle=30 * DAY)
    report = await hkp.sweep_intermediates(hk.ctx, other, clock=clock)
    assert report.projects == []
    assert len(hk.blobs.list(f"work/{mine}")) == 4


async def test_free_this_project_now_ignores_the_ttl_but_not_a_running_job(hk: Hk) -> None:
    fresh = await hk.project(idle=timedelta(0))
    busy = await hk.project(status="planning")
    await hk.job(busy, stage="draft", state="running")
    await hkp.sweep_intermediates(hk.ctx, hk.user, project_id=busy, clock=clock)
    assert len(hk.blobs.list(f"work/{busy}")) == 4
    report = await hkp.sweep_intermediates(hk.ctx, hk.user, project_id=fresh, clock=clock)
    assert report.projects == [fresh]
    assert not hk.has(f"work/{fresh}")
    assert hk.has(f"songs/{fresh}")


def age(hk: Hk, key: str, hours: float) -> None:
    path = hk.blobs.local_path(key)
    stamp = NOW.timestamp() - hours * 3600
    os.utime(path, (stamp, stamp))


async def test_abandoned_uploads_are_reaped_at_24_hours(hk: Hk) -> None:
    old, fresh, busy, idle = (
        await hk.project(status="created", files=False),
        await hk.project(status="created", files=False),
        await hk.project(status="validating", files=False),
        await hk.project(status="rejected", files=False),
    )
    for pid, name, hours in (
        (old, "incoming.bin.part", 25),
        (fresh, "incoming.bin.part", 23),
        (busy, "incoming.bin", 48),  # a validating project still needs its upload
        (idle, "incoming.bin", 25),
    ):
        hk.put(f"songs/{pid}/{name}", b"u" * 10)
        age(hk, f"songs/{pid}/{name}", hours)
    hk.put(f"songs/{old}/source.wav", b"s" * 10)
    age(hk, f"songs/{old}/source.wav", 500)  # a kept song is never reaped by age

    freed = await hkp.reap_abandoned_uploads(hk.ctx, hk.user, clock=clock)

    assert freed == 20
    assert hk.blobs.list(f"songs/{old}") == [f"songs/{old}/source.wav"]
    assert hk.has(f"songs/{fresh}/incoming.bin.part")
    assert hk.has(f"songs/{busy}/incoming.bin")
    assert not hk.has(f"songs/{idle}/incoming.bin")


async def test_an_orphan_directory_goes_only_on_the_second_sighting(hk: Hk) -> None:
    real = await hk.project()
    ghost = "00000000-0000-4000-8000-00000000dead"
    for key in (
        f"songs/{ghost}/source.wav",
        f"work/{ghost}/raw/a.mp4",
        f"renders/{ghost}/master.mp4",
    ):
        hk.put(key)
    first = await hkp.reconcile_orphans(hk.ctx, hk.user, hk.redis)
    assert first["removed"] == []
    assert sorted(first["seen"]) == sorted(f"{t}/{ghost}" for t in ("songs", "work", "renders"))
    assert hk.has(f"songs/{ghost}")
    second = await hkp.reconcile_orphans(hk.ctx, hk.user, hk.redis)
    assert sorted(second["removed"]) == sorted(first["seen"])
    for top in ("songs", "work", "renders"):
        assert not hk.has(f"{top}/{ghost}")
    assert hk.has(f"songs/{real}")  # a real project is never an orphan
    assert hk.has(f"work/{real}")


async def test_another_users_directories_are_not_orphans(hk: Hk) -> None:
    other = UUID("00000000-0000-4000-8000-0000000000cc")
    await insert_user(hk.db, other, "c@example.test")
    theirs = await hk.project(user=other)
    their_render = new_id()
    await hk.sql(
        "INSERT INTO edit_plans (id, project_id, version, schema_version, plan, content_hash,"
        " created_by) VALUES ($1,$2,1,'1','{}',$3,'planner')",
        new_id(),
        theirs,
        b"h" * 32,
    )
    plan = (await hk.sql("SELECT id FROM edit_plans WHERE project_id=$1", theirs))[0][0]
    await hk.sql(
        "INSERT INTO renders (id, project_id, edit_plan_id, user_id, job_hash, state)"
        " VALUES ($1,$2,$3,$4,$5,'ready')",
        their_render,
        theirs,
        plan,
        other,
        b"r" * 32,
    )
    hk.put(f"renders/{their_render}/master.mp4")
    ghost = "00000000-0000-4000-8000-00000000dead"
    hk.put(f"songs/{ghost}/source.wav")

    for _ in range(2):  # two consecutive passes: the second is the one that deletes
        await hkp.reconcile_orphans(hk.ctx, hk.user, hk.redis)

    assert not hk.has(f"songs/{ghost}")  # a true orphan is gone
    assert hk.has(f"songs/{theirs}")
    assert hk.has(f"work/{theirs}")
    assert hk.has(f"renders/{their_render}")


async def test_a_transition_makes_a_swept_project_sweepable_again(hk: Hk) -> None:
    pid = await hk.project(idle=8 * DAY)
    await hkp.sweep_intermediates(hk.ctx, hk.user, clock=clock)
    assert not hk.has(f"work/{pid}")
    async with hk.ctx.sessionmaker() as session:  # a replan rebuilds `work/`
        moved = await ProjectRepository(session).transition(
            user_id=hk.user, project_id=pid, from_="draft_ready", to="planning"
        )
        await session.commit()
    assert moved
    hk.put(f"work/{pid}/mezz/pexels_2.mp4")
    await hk.sql("UPDATE projects SET last_activity_at=$2 WHERE id=$1", pid, NOW - 8 * DAY)

    report = await hkp.sweep_intermediates(hk.ctx, hk.user, clock=clock)

    assert report.projects == [pid]
    assert not hk.has(f"work/{pid}")


async def test_one_failing_purge_does_not_stop_the_next_one(
    hk: Hk, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = await hk.project(status="deleted")
    second = await hk.project(status="deleted")
    real = hkp.purge_project
    calls: list[UUID] = []

    async def flaky(ctx: WorkerContext, user_id: UUID, project_id: UUID) -> None:
        calls.append(project_id)
        if len(calls) == 1:
            msg = "disk went away"
            raise OSError(msg)
        await real(ctx, user_id, project_id)

    monkeypatch.setattr(hkp, "purge_project", flaky)

    report = await hkp.sweep_intermediates(hk.ctx, hk.user, clock=clock)

    assert set(calls) == {first, second}
    survivor, failed = calls[1], calls[0]
    assert report.purged == [survivor]
    assert not hk.has(f"songs/{survivor}")
    assert hk.has(f"songs/{failed}")


async def test_prune_jobs_keeps_young_and_unfinished_jobs(hk: Hk) -> None:
    pid = await hk.project()
    old = await hk.job(pid, state="ok", finished_age=91 * DAY)
    young = await hk.job(pid, state="ok", finished_age=89 * DAY)
    dead_old = await hk.job(pid, state="dead", finished_age=200 * DAY)
    running = await hk.job(pid, state="running", age=300 * DAY)
    assert await hkp.prune_jobs(hk.ctx, hk.user, clock=clock) == 2
    left = {r[0] for r in await hk.sql("SELECT id FROM jobs WHERE project_id=$1", pid)}
    assert left == {young, running}
    assert old not in left
    assert dead_old not in left


async def test_a_stuck_queued_job_is_resent_twice_then_dies(hk: Hk) -> None:
    pid = await hk.project(status="validating")
    young = await hk.job(pid, stage="analyze", age=timedelta(seconds=STUCK_QUEUED_S - 60))
    job = await hk.job(pid, stage="validate", age=timedelta(minutes=11))
    for n in range(1, MAX_RESENDS + 1):
        assert await hkp.reap_stuck_jobs(hk.ctx, hk.user, hk.redis, clock=clock) == [job]
        assert hk.enqueuer.sent[-1] == ("validate_audio", (str(job), str(hk.user)))
        assert len(hk.enqueuer.sent) == n
        await hk.sql("UPDATE jobs SET updated_at=$2 WHERE id=$1", job, NOW - timedelta(minutes=11))
    assert await hkp.reap_stuck_jobs(hk.ctx, hk.user, hk.redis, clock=clock) == [job]
    assert len(hk.enqueuer.sent) == MAX_RESENDS  # the third is refused
    state = (await hk.sql("SELECT state FROM jobs WHERE id=$1", job))[0][0]
    assert state == "dead"
    status = (await hk.sql("SELECT status FROM projects WHERE id=$1", pid))[0][0]
    assert status == "failed_analysis"
    assert (await hk.sql("SELECT state FROM jobs WHERE id=$1", young))[0][0] == "queued"


async def test_a_running_job_past_three_slot_lifetimes_is_stuck(hk: Hk) -> None:
    fine_project = await hk.project(status="planning")
    stuck_project = await hk.project(status="planning")
    await hk.job(fine_project, stage="draft", state="running", age=timedelta(minutes=30))
    dead = await hk.job(stuck_project, stage="replan", state="running", age=timedelta(hours=1))
    assert await hkp.reap_stuck_jobs(hk.ctx, hk.user, hk.redis, clock=clock) == [dead]
    assert [args[0] for _, args in hk.enqueuer.sent] == [str(dead)]


async def test_audit_stale_is_non_empty_before_a_sweep_and_empty_after(hk: Hk) -> None:
    pid = await hk.project(idle=TTL + timedelta(hours=2))
    await hk.project(idle=TTL + timedelta(minutes=30))  # inside the one-hour grace
    assert await hkp.audit_stale(hk.ctx, hk.user, clock=clock) == [f"work/{pid}"]
    await hkp.sweep_intermediates(hk.ctx, hk.user, clock=clock)
    assert await hkp.audit_stale(hk.ctx, hk.user, clock=clock) == []


async def test_purge_never_touches_a_live_project(hk: Hk) -> None:
    pid = await hk.project(status="ready")
    before = snapshot(hk, "songs", "work")
    await hkp.purge_project(hk.ctx, hk.user, pid)
    assert snapshot(hk, "songs", "work") == before
    assert (await hk.sql("SELECT count(*) FROM projects WHERE id=$1", pid))[0][0] == 1


async def test_purge_waits_for_a_running_job(hk: Hk) -> None:
    pid = await hk.project(status="deleted")
    await hk.job(pid, stage="render", state="running")
    with pytest.raises(PurgeBusy):
        await hkp.purge_project(hk.ctx, hk.user, pid)
    assert hk.has(f"songs/{pid}")
    await hk.sql("UPDATE jobs SET state='error', finished_at=now() WHERE project_id=$1", pid)
    await hkp.purge_project(hk.ctx, hk.user, pid)
    assert not hk.has(f"songs/{pid}")


async def test_the_transition_bumps_activity_and_stamps_deletion(hk: Hk) -> None:
    pid = await hk.project(status="ready", idle=30 * DAY)
    async with hk.ctx.sessionmaker() as session:
        from saveclock.repositories.projects import ProjectRepository

        repo = ProjectRepository(session)
        assert await repo.transition(user_id=hk.user, project_id=pid, from_="ready", to="deleted")
        await session.commit()
    row = (await hk.sql("SELECT last_activity_at, deleted_at FROM projects WHERE id=$1", pid))[0]
    assert row["last_activity_at"].timestamp() > time.time() - 60
    assert row["deleted_at"] is not None


async def test_a_hard_delete_refuses_a_live_project(hk: Hk, tmp_path: Path) -> None:
    pid = await hk.project(status="ready")
    async with hk.ctx.sessionmaker() as session:
        from saveclock.repositories.projects import ProjectRepository

        assert not await ProjectRepository(session).hard_delete(user_id=hk.user, project_id=pid)
    assert (await hk.sql("SELECT count(*) FROM projects WHERE id=$1", pid))[0][0] == 1


async def test_a_stuck_job_of_a_stage_with_no_actor_goes_straight_to_dead(hk: Hk) -> None:
    pid = await hk.project(status="planning")
    job = await hk.job(pid, stage="rehydrate", state="running", age=timedelta(hours=2))
    assert await hkp.reap_stuck_jobs(hk.ctx, hk.user, hk.redis, clock=clock) == [job]
    assert hk.enqueuer.sent == []
    assert (await hk.sql("SELECT state FROM jobs WHERE id=$1", job))[0][0] == "dead"


async def test_dry_runs_and_a_purge_of_a_missing_project_do_nothing(hk: Hk) -> None:
    await hkp.purge_project(hk.ctx, hk.user, UUID(int=99))  # no such project: a no-op
    assert await hkp.reap_abandoned_uploads(hk.ctx, hk.user, dry_run=True, clock=clock) == 0
    report = await hkp.reconcile_orphans(hk.ctx, hk.user, hk.redis, dry_run=True)
    assert report == {"seen": [], "removed": []}

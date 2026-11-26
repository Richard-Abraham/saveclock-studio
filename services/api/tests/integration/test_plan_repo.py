"""PlanRepository and the candidate pool queries against real Postgres."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from saveclock.repositories.candidates import CandidateRepository
from saveclock.repositories.plans import PlanRepository, PlanVersionExists
from tests.integration.conftest import ApiEnv
from tests.integration.draft_harness import OWNER, Draft

pytestmark = pytest.mark.integration
STRANGER = UUID("00000000-0000-4000-8000-0000000000bb")


async def test_latest_and_versions_are_read_for_the_owner_only(draft: Draft) -> None:
    pid = await draft.drafted()
    async with draft.ctx.sessionmaker() as session:
        plans = PlanRepository(session)
        latest = await plans.latest(user_id=OWNER, project_id=pid)
        assert latest is not None
        assert latest.version == 1
        assert await plans.get_version(user_id=OWNER, project_id=pid, version=1) is not None
        assert await plans.get_version(user_id=OWNER, project_id=pid, version=2) is None
        assert await plans.latest(user_id=STRANGER, project_id=pid) is None
        assert await plans.get_version(user_id=STRANGER, project_id=pid, version=1) is None


async def test_a_version_taken_twice_raises_and_keeps_the_session_usable(draft: Draft) -> None:
    pid = await draft.drafted()
    plan = await draft.plan(pid)
    async with draft.ctx.sessionmaker() as session:
        plans = PlanRepository(session)
        with pytest.raises(PlanVersionExists):
            await plans.insert(
                user_id=OWNER,
                project_id=pid,
                plan_id=uuid4(),
                version=1,
                schema_version="1.0",
                plan=plan.model_dump(mode="json"),
                content_hash=b"\x00" * 32,
                created_by="planner",
            )
        await plans.insert(  # the savepoint rolled back: the transaction still works
            user_id=OWNER,
            project_id=pid,
            plan_id=uuid4(),
            version=2,
            schema_version="1.0",
            plan=plan.model_dump(mode="json"),
            content_hash=b"\x01" * 32,
            created_by="user",
        )
        await session.commit()
    assert [r[0] for r in await draft.sql("SELECT version FROM edit_plans ORDER BY version")] == [
        1,
        2,
    ]


async def test_insert_for_a_foreign_project_writes_nothing(draft: Draft) -> None:
    pid = await draft.drafted()
    plan = await draft.plan(pid)
    async with draft.ctx.sessionmaker() as session:
        await PlanRepository(session).insert(
            user_id=STRANGER,
            project_id=pid,
            plan_id=uuid4(),
            version=2,
            schema_version="1.0",
            plan=plan.model_dump(mode="json"),
            content_hash=b"\x01" * 32,
            created_by="user",
        )
        await session.commit()
    assert len(await draft.sql("SELECT 1 FROM edit_plans")) == 1


async def test_replace_working_stops_at_a_frozen_version_and_at_a_stranger(draft: Draft) -> None:
    pid = await draft.drafted()
    plan = await draft.plan(pid)
    row = (await draft.sql("SELECT id FROM edit_plans"))[0]
    args = {
        "project_id": pid,
        "plan_id": row[0],
        "plan": plan.model_dump(mode="json"),
        "content_hash": b"\x07" * 32,
        "created_by": "user",
    }
    async with draft.ctx.sessionmaker() as session:
        plans = PlanRepository(session)
        assert not await plans.replace_working(user_id=STRANGER, **args)
        assert await plans.replace_working(user_id=OWNER, **args)
        await session.commit()
    assert bytes((await draft.sql("SELECT content_hash FROM edit_plans"))[0][0]) == b"\x07" * 32
    await draft.freeze(pid)
    async with draft.ctx.sessionmaker() as session:
        assert not await PlanRepository(session).replace_working(
            user_id=OWNER, **{**args, "content_hash": b"\x08" * 32}
        )
    assert bytes((await draft.sql("SELECT content_hash FROM edit_plans"))[0][0]) == b"\x07" * 32


async def test_the_pool_and_the_selection(draft: Draft) -> None:
    pid = await draft.drafted()
    async with draft.ctx.sessionmaker() as session:
        repo = CandidateRepository(session)
        pool = await repo.list_pool(user_id=OWNER, project_id=pid)
        assert pool
        assert all(c.status in {"normalized", "selected"} and c.mezz_frames for c in pool)
        scores = [c.score or 0.0 for c in pool]
        assert scores == sorted(scores, reverse=True)
        assert await repo.list_pool(user_id=STRANGER, project_id=pid) == []
        keep = {(pool[0].provider, pool[0].provider_id)}
        await repo.mark_selected(user_id=STRANGER, project_id=pid, keys=keep)  # not the owner's
        await repo.mark_selected(user_id=OWNER, project_id=pid, keys=keep)
        await session.commit()
    rows = await draft.sql(
        "SELECT provider_id, status FROM clip_candidates WHERE status IN ('selected','normalized')"
    )
    assert [r[0] for r in rows if r[1] == "selected"] == [pool[0].provider_id]
    async with draft.ctx.sessionmaker() as session:
        await CandidateRepository(session).mark_selected(user_id=OWNER, project_id=pid, keys=[])
        await session.commit()
    assert "selected" not in {
        r[1] for r in await draft.sql("SELECT provider_id, status FROM clip_candidates")
    }


async def test_a_second_engine_sees_the_same_rows(api: ApiEnv) -> None:
    engine = create_async_engine(api.db.url("app_rw"), poolclass=NullPool)
    try:
        async with async_sessionmaker(engine)() as session:
            assert await PlanRepository(session).latest(user_id=OWNER, project_id=uuid4()) is None
    finally:
        await engine.dispose()

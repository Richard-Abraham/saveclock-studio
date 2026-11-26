"""CandidateRepository against a real database: ownership on every method (SEC: a user id)."""

from uuid import UUID, uuid4

import pytest

from saveclock.repositories.candidates import CandidateRepository, NewCandidate
from tests.integration.footage_harness import OWNER, Footage

pytestmark = pytest.mark.integration


def candidate(i: int, query: str = "red") -> NewCandidate:
    return NewCandidate(
        "pexels",
        f"id-{i}",
        query,
        "https://www.pexels.com/video/x/",
        "A",
        None,
        "Pexels License",
        1080,
        1920,
        7.5,
        29.97,
        f"https://videos.pexels.com/{i}.mp4",
    )


async def repo_rows(footage: Footage, user: UUID, pid: UUID) -> int:
    async with footage.ctx.sessionmaker() as session:
        return len(
            await CandidateRepository(session).list_for_project(user_id=user, project_id=pid)
        )


async def test_upsert_is_idempotent_and_never_overwrites_a_vetted_row(footage: Footage) -> None:
    async with footage.ctx.sessionmaker() as session:
        repo = CandidateRepository(session)
        assert (
            await repo.upsert_found(
                user_id=OWNER, project_id=footage.pid, found=[candidate(1), candidate(2)]
            )
            == 2
        )
        await session.commit()
        assert await repo.mark(
            user_id=OWNER,
            project_id=footage.pid,
            provider="pexels",
            provider_id="id-1",
            status="ranked",
            score=0.5,
            window_start_s=1,
            mezz_frames=90,
        )
        await session.commit()
        again = await repo.upsert_found(
            user_id=OWNER, project_id=footage.pid, found=[candidate(1, "other"), candidate(3)]
        )
        await session.commit()
        assert again == 1  # only id-3 is new
        row = await repo.get_by_provider_id(
            user_id=OWNER, project_id=footage.pid, provider="pexels", provider_id="id-1"
        )
    assert row is not None
    assert (row.status, row.query, row.mezz_frames) == ("ranked", "red", 90)
    assert float(row.duration_s or 0) == 7.5
    assert row.fps == pytest.approx(29.97, abs=0.01)


async def test_list_filters_by_status_and_orders_stably(footage: Footage) -> None:
    async with footage.ctx.sessionmaker() as session:
        repo = CandidateRepository(session)
        await repo.upsert_found(
            user_id=OWNER, project_id=footage.pid, found=[candidate(i) for i in (3, 1, 2)]
        )
        await repo.mark(
            user_id=OWNER,
            project_id=footage.pid,
            provider="pexels",
            provider_id="id-2",
            status="ranked",
        )
        await session.commit()
        everything = await repo.list_for_project(user_id=OWNER, project_id=footage.pid)
        ranked = await repo.list_for_project(
            user_id=OWNER, project_id=footage.pid, statuses=["ranked"]
        )
        none = await repo.list_for_project(user_id=OWNER, project_id=footage.pid, statuses=[])
    assert [r.provider_id for r in everything] == ["id-1", "id-2", "id-3"]
    assert [r.provider_id for r in ranked] == ["id-2"]
    assert none == []


async def test_download_urls_are_nulled_only_after_the_file_is_ours(footage: Footage) -> None:
    async with footage.ctx.sessionmaker() as session:
        repo = CandidateRepository(session)
        await repo.upsert_found(
            user_id=OWNER, project_id=footage.pid, found=[candidate(1), candidate(2)]
        )
        await repo.mark(
            user_id=OWNER,
            project_id=footage.pid,
            provider="pexels",
            provider_id="id-1",
            status="downloaded",
        )
        await session.commit()
        assert await repo.null_download_urls(user_id=OWNER, project_id=footage.pid) == 1
        await session.commit()
        rows = {
            r.provider_id: r.download_url
            for r in await repo.list_for_project(user_id=OWNER, project_id=footage.pid)
        }
    assert rows["id-1"] is None
    assert rows["id-2"] is not None  # still `found`: the URL is needed for the download


async def test_a_second_user_sees_nothing_and_changes_nothing(footage: Footage) -> None:
    other = uuid4()
    async with footage.ctx.sessionmaker() as session:
        repo = CandidateRepository(session)
        await repo.upsert_found(user_id=OWNER, project_id=footage.pid, found=[candidate(1)])
        await session.commit()
        assert (
            await repo.upsert_found(user_id=other, project_id=footage.pid, found=[candidate(9)])
            == 0
        )
        await session.commit()
        assert await repo.list_for_project(user_id=other, project_id=footage.pid) == []
        assert not await repo.mark(
            user_id=other,
            project_id=footage.pid,
            provider="pexels",
            provider_id="id-1",
            status="selected",
        )
        assert await repo.null_download_urls(user_id=other, project_id=footage.pid) == 0
    assert await repo_rows(footage, OWNER, footage.pid) == 1
    async with footage.ctx.sessionmaker() as session:
        row = await CandidateRepository(session).get_by_provider_id(
            user_id=OWNER, project_id=footage.pid, provider="pexels", provider_id="id-1"
        )
    assert row is not None
    assert row.status == "found"


async def test_a_project_of_another_user_cannot_be_written_to(footage: Footage) -> None:
    async with footage.ctx.sessionmaker() as session:
        repo = CandidateRepository(session)
        assert await repo.upsert_found(user_id=OWNER, project_id=uuid4(), found=[candidate(1)]) == 0

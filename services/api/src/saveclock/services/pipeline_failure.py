"""A job whose retries are exhausted (or that the reaper gives up on) is dead and its project fails.

One body, two callers: the Dramatiq `pipeline_failed` hook and the stuck-job reaper.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.adapters.events import EventPublisher
from saveclock.models import JobStage, ProjectStatus
from saveclock.repositories.jobs import JobRepository
from saveclock.repositories.plans import PlanRepository
from saveclock.services import project_state
from saveclock.services.plans import restore_keywords_override
from saveclock.services.render_job import render_job_died


async def job_died(
    session: AsyncSession, publisher: EventPublisher | None, user_id: UUID, job_id: UUID
) -> None:
    """Retries exhausted: the job is dead and the project failed (`validating|analyzing` only).
    A render or remux job also ends its render (`services.render_job.render_job_died`)."""
    jobs = JobRepository(session)
    job = await jobs.get(user_id=user_id, job_id=job_id)
    await jobs.mark_dead(user_id=user_id, job_id=job_id)
    if job is not None and job.project_id is not None:
        planned = (
            await PlanRepository(session).latest(user_id=user_id, project_id=job.project_id)
            is not None
        )
        # a replan that dies keeps the plan the owner had (and drops its keywords)
        planning_to = ProjectStatus.DRAFT_READY if planned else ProjectStatus.FAILED_PLAN
        for from_, to in (
            (ProjectStatus.VALIDATING, ProjectStatus.FAILED_ANALYSIS),
            (ProjectStatus.ANALYZING, ProjectStatus.FAILED_ANALYSIS),
            (ProjectStatus.PLANNING, planning_to),  # the draft job
        ):
            moved = await project_state.transition(
                session,
                publisher,
                user_id=user_id,
                project_id=job.project_id,
                from_=from_.value,
                to=to.value,
                reason="retries_exhausted",
                commit=False,
            )
            if moved and planned and to is ProjectStatus.DRAFT_READY:
                await restore_keywords_override(session, user_id, job.project_id)
    if job is not None and job.stage in {JobStage.RENDER.value, JobStage.REMUX.value}:
        await render_job_died(session, publisher, user_id, job)  # plan 007
    await session.commit()
    await project_state.announce_pending(session, publisher)

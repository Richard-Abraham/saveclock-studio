"""Importing the package registers every model on `Base.metadata` (Alembic relies on it)."""

from saveclock.models.analysis import Analysis, Fallback
from saveclock.models.base import Base
from saveclock.models.clip_candidate import ClipCandidate, ClipStatus, Provider
from saveclock.models.edit_plan import EditPlan, PlanCreator
from saveclock.models.job import Job, JobQueue, JobStage, JobState
from saveclock.models.project import Project, ProjectStatus
from saveclock.models.render import ModeAState, Render, RenderState
from saveclock.models.song import Song
from saveclock.models.user import User

__all__ = [
    "Analysis",
    "Base",
    "ClipCandidate",
    "ClipStatus",
    "EditPlan",
    "Fallback",
    "Job",
    "JobQueue",
    "JobStage",
    "JobState",
    "ModeAState",
    "PlanCreator",
    "Project",
    "ProjectStatus",
    "Provider",
    "Render",
    "RenderState",
    "Song",
    "User",
]

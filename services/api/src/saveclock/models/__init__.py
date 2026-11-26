"""Importing the package registers every model on `Base.metadata` (Alembic relies on it)."""

from saveclock.models.base import Base
from saveclock.models.job import Job, JobQueue, JobStage, JobState
from saveclock.models.project import Project, ProjectStatus
from saveclock.models.song import Song
from saveclock.models.user import User

__all__ = [
    "Base",
    "Job",
    "JobQueue",
    "JobStage",
    "JobState",
    "Project",
    "ProjectStatus",
    "Song",
    "User",
]

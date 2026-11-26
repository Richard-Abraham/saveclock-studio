"""Schemas of the named stub routes. Phase 2 deletes this file."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StubJobIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sleep_s: int = Field(default=0, ge=0, le=30)


class StubJobOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: UUID
    project_id: UUID


class StubHop(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: UUID
    queue: str
    stage: str
    state: str
    attempt: int
    run_ms: int | None


class StubChain(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: UUID
    project_id: UUID
    hops: list[StubHop]

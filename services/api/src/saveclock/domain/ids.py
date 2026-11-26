"""Deterministic job ids: a retry or a redelivery derives the same child id (idempotent enqueue)."""

from uuid import UUID, uuid5

NAMESPACE = UUID("5a5e0000-0000-4000-8000-5ab000000002")


def derive_job_id(parent: UUID, stage: str) -> UUID:
    return uuid5(NAMESPACE, f"{parent}:{stage}")

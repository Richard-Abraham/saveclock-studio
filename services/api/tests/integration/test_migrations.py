"""0001_baseline against a real Postgres. Expected values are the DDL literals from plan 001."""

import re
from typing import Any

import asyncpg
import pytest

from saveclock.models import JobQueue, JobStage, JobState, ProjectStatus
from tests.integration.conftest import OWNER_NAME, Db

pytestmark = pytest.mark.integration

OWNER_ID = "00000000-0000-4000-8000-000000000001"
TS = "timestamp with time zone"
NOW = "now()"
EMPTY = "'{}'::jsonb"

# column -> (type, nullable, default)
COLUMNS: dict[str, dict[str, tuple[str, bool, str | None]]] = {
    "users": {
        "id": ("uuid", False, None),
        "email": ("text", False, None),
        "display_name": ("text", True, None),
        "settings": ("jsonb", False, EMPTY),
        "created_at": (TS, False, NOW),
        "updated_at": (TS, False, NOW),
    },
    "projects": {
        "id": ("uuid", False, None),
        "user_id": ("uuid", False, None),
        "title": ("text", True, None),
        "status": ("text", False, "'created'::text"),
        "status_reason": ("text", True, None),
        "flags": ("jsonb", False, EMPTY),
        "options": ("jsonb", False, EMPTY),
        "upload_completed_at": (TS, True, None),
        "last_activity_at": (TS, False, NOW),
        "intermediates_purged_at": (TS, True, None),
        "manual_retries": ("smallint", False, "0"),
        "deleted_at": (TS, True, None),
        "created_at": (TS, False, NOW),
        "updated_at": (TS, False, NOW),
    },
    "songs": {
        "id": ("uuid", False, None),
        "project_id": ("uuid", False, None),
        "original_filename": ("text", False, None),
        "size_bytes": ("bigint", False, None),
        "content_type": ("text", False, None),
        "duration_s": ("numeric(8,3)", True, None),
        "codec": ("text", True, None),
        "sample_rate": ("integer", True, None),
        "channels": ("smallint", True, None),
        "sha256": ("bytea", True, None),
        "source_ext": ("text", True, None),
        "created_at": (TS, False, NOW),
        "updated_at": (TS, False, NOW),
    },
    "jobs": {
        "id": ("uuid", False, None),
        "project_id": ("uuid", True, None),
        "render_id": ("uuid", True, None),
        "stage": ("text", False, None),
        "queue": ("text", False, None),
        "attempt": ("smallint", False, "0"),
        "state": ("text", False, "'queued'::text"),
        "error_code": ("text", True, None),
        "error_detail": ("text", True, None),
        "started_at": (TS, True, None),
        "finished_at": (TS, True, None),
        "timings": ("jsonb", False, EMPTY),
        "cancel_requested": ("boolean", False, "false"),
        "created_at": (TS, False, NOW),
        "updated_at": (TS, False, NOW),
    },
}

INDEXES = {
    "ix_projects_user_id_created_at",
    "ix_projects_status",
    "ix_projects_last_activity_at",
    "ix_songs_sha256",
    "ix_jobs_project_id_stage",
    "ix_jobs_state",
}  # + pk/uq indexes; the notice counts the 3 + 1 + 2 secondary indexes and the unique ones below
CONSTRAINTS = {
    "pk_users", "uq_users_email",
    "pk_projects", "fk_projects_user_id_users", "ck_projects_status", "ck_projects_manual_retries",
    "pk_songs", "fk_songs_project_id_projects", "uq_songs_project_id", "ck_songs_size_bytes",
    "ck_songs_sha256_len",
    "pk_jobs", "fk_jobs_project_id_projects", "ck_jobs_stage", "ck_jobs_queue", "ck_jobs_state",
}  # fmt: skip
TABLES = {"alembic_version", "users", "projects", "songs", "jobs"}


async def snapshot(db: Db) -> dict[str, Any]:
    conn = await asyncpg.connect(db.raw("postgres"))
    try:
        tables = {
            r[0]
            for r in await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        }
        columns: dict[str, dict[str, tuple[str, bool, str | None]]] = {}
        for t in tables - {"alembic_version"}:
            rows = await conn.fetch(
                """SELECT a.attname, format_type(a.atttypid, a.atttypmod), NOT a.attnotnull,
                          pg_get_expr(d.adbin, d.adrelid)
                   FROM pg_attribute a
                   LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
                   WHERE a.attrelid = ('public.' || $1)::regclass AND a.attnum > 0
                     AND NOT a.attisdropped""",
                t,
            )
            columns[t] = {r[0]: (r[1], r[2], r[3]) for r in rows}
        indexes = {
            r["indexname"]: r["indexdef"]
            for r in await conn.fetch(
                "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public'"
                " AND indexname LIKE 'ix\\_%'"
            )
        }
        constraints = {
            r[0]
            for r in await conn.fetch(
                "SELECT conname FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid"
                " WHERE t.relnamespace = 'public'::regnamespace AND t.relname <> 'alembic_version'"
                " AND contype IN ('p','u','f','c')"
            )
        }
        return {
            "tables": tables,
            "columns": columns,
            "indexes": indexes,
            "constraints": constraints,
        }
    finally:
        await conn.close()


async def test_upgrade_matches_the_ddl(migrated_db: Db) -> None:
    snap = await snapshot(migrated_db)
    assert snap["tables"] == TABLES
    for table, expected in COLUMNS.items():
        for column, spec in expected.items():
            assert snap["columns"][table].get(column) == spec, f"{table}.{column}"
        assert set(snap["columns"][table]) == set(expected), table
    assert set(snap["indexes"]) == INDEXES
    assert snap["constraints"] == CONSTRAINTS
    ix = snap["indexes"]
    assert "created_at DESC" in ix["ix_projects_user_id_created_at"]
    assert "WHERE (status <> 'deleted'::text)" in ix["ix_projects_status"]
    assert "WHERE (intermediates_purged_at IS NULL)" in ix["ix_projects_last_activity_at"]
    assert "WHERE (state = ANY (ARRAY['queued'::text, 'running'::text]))" in ix["ix_jobs_state"]


async def test_owner_row_is_seeded_once(migrated_db: Db) -> None:
    again = migrated_db.alembic("upgrade", "head")
    assert again.returncode == 0, again.stderr
    conn = await asyncpg.connect(migrated_db.raw("postgres"))
    try:
        rows = await conn.fetch("SELECT id::text, email, display_name FROM users")
    finally:
        await conn.close()
    assert [tuple(r) for r in rows] == [(OWNER_ID, "owner@saveclock.local", OWNER_NAME)]


async def test_alembic_check_and_roundtrip(migrated_db: Db) -> None:
    before = await snapshot(migrated_db)
    check = migrated_db.alembic("check")
    assert check.returncode == 0, check.stdout + check.stderr
    down = migrated_db.alembic("downgrade", "base")
    assert down.returncode == 0, down.stderr
    assert (await snapshot(migrated_db))["tables"] == {"alembic_version"}
    up = migrated_db.alembic("upgrade", "head")
    assert up.returncode == 0, up.stderr
    assert await snapshot(migrated_db) == before


async def test_heads(migrated_db: Db) -> None:
    out = migrated_db.alembic("heads")
    assert out.stdout.strip() == "0001_baseline (head)"


async def test_missing_owner_name_fails_clearly(fresh_db: Db) -> None:
    done = fresh_db.alembic("upgrade", "head", owner=None)
    assert done.returncode != 0
    assert "OWNER_DISPLAY_NAME" in done.stderr


async def test_check_constraints_agree_with_python_enums(migrated_db: Db) -> None:
    conn = await asyncpg.connect(migrated_db.raw("postgres"))
    try:
        expected = {
            "ck_projects_status": {m.value for m in ProjectStatus},
            "ck_jobs_stage": {m.value for m in JobStage},
            "ck_jobs_queue": {m.value for m in JobQueue},
            "ck_jobs_state": {m.value for m in JobState},
        }
        for name, values in expected.items():
            definition = await conn.fetchval(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = $1", name
            )
            assert set(re.findall(r"'([a-z_]+)'::text", definition)) == values, name
    finally:
        await conn.close()


async def test_role_boundary(migrated_db: Db) -> None:
    app = await asyncpg.connect(migrated_db.raw("app_rw"))
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app.execute("CREATE TABLE x (i int)")
        await app.execute(
            "INSERT INTO users (id, email) VALUES ('00000000-0000-4000-8000-0000000000aa', 'a@b.c')"
        )
        assert await app.fetchval("SELECT count(*) FROM users") == 2
    finally:
        await app.close()
    migrator = await asyncpg.connect(migrated_db.raw("migrator"))
    try:
        await migrator.execute("CREATE TABLE y (i int)")
    finally:
        await migrator.close()


async def test_later_tables_do_not_exist_yet(migrated_db: Db) -> None:
    conn = await asyncpg.connect(migrated_db.raw("postgres"))
    try:
        assert await conn.fetchval("SELECT to_regclass('renders')") is None
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM pg_indexes WHERE indexname = 'uq_jobs_active'"
            )
            == 0
        )
    finally:
        await conn.close()

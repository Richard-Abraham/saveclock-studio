"""0001_baseline against a real Postgres. Expected values are the DDL literals from plan 001."""

import re
import uuid
from typing import Any

import asyncpg
import pytest

from saveclock.models import (
    ClipStatus,
    Fallback,
    JobQueue,
    JobStage,
    JobState,
    ModeAState,
    PlanCreator,
    ProjectStatus,
    Provider,
    RenderState,
)
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

COLUMNS["analyses"] = {
    "id": ("uuid", False, None),
    "song_id": ("uuid", False, None),
    "model": ("text", False, None),
    "model_version": ("text", False, None),
    "tempo_bpm": ("numeric(6,2)", False, None),
    "tempo_octave_adjust": ("smallint", False, "0"),
    "beat_confidence": ("real", False, None),
    "fallback": ("text", True, None),
    "beat_map": ("jsonb", False, None),
    "sections": ("jsonb", False, None),
    "energy_curve": ("jsonb", False, None),
    "waveform_peaks": ("jsonb", False, None),
    "low_confidence_ranges": ("jsonb", False, "'[]'::jsonb"),
    "timing": ("jsonb", False, EMPTY),
    "created_at": (TS, False, NOW),
    "updated_at": (TS, False, NOW),
}
COLUMNS["clip_candidates"] = {
    "id": ("uuid", False, None),
    "project_id": ("uuid", False, None),
    "provider": ("text", False, None),
    "provider_id": ("text", False, None),
    "query": ("text", False, None),
    "page_url": ("text", False, None),
    "author": ("text", True, None),
    "author_url": ("text", True, None),
    "license": ("text", False, None),
    "fetched_at": (TS, False, NOW),
    "width": ("integer", True, None),
    "height": ("integer", True, None),
    "duration_s": ("numeric(7,3)", True, None),
    "fps": ("real", True, None),
    "download_url": ("text", True, None),
    "status": ("text", False, "'found'::text"),
    "reject_reason": ("text", True, None),
    "score": ("real", True, None),
    "frame_scores": ("jsonb", True, None),
    "window_start_s": ("numeric(7,3)", True, None),
    "mezz_frames": ("integer", True, None),
    "created_at": (TS, False, NOW),
    "updated_at": (TS, False, NOW),
}
COLUMNS["edit_plans"] = {
    "id": ("uuid", False, None),
    "project_id": ("uuid", False, None),
    "version": ("integer", False, None),
    "schema_version": ("text", False, None),
    "plan": ("jsonb", False, None),
    "content_hash": ("bytea", False, None),
    "created_by": ("text", False, None),
    "frozen_at": (TS, True, None),
    "created_at": (TS, False, NOW),
    "updated_at": (TS, False, NOW),
}
COLUMNS["renders"] = {
    "id": ("uuid", False, None),
    "project_id": ("uuid", False, None),
    "edit_plan_id": ("uuid", False, None),
    "user_id": ("uuid", False, None),
    "job_hash": ("bytea", False, None),
    "state": ("text", False, "'queued'::text"),
    "attempt": ("smallint", False, "0"),
    "error_code": ("text", True, None),
    "size_bytes": ("bigint", True, None),
    "duration_frames": ("integer", True, None),
    "verify": ("jsonb", False, EMPTY),
    "render_ms": ("integer", True, None),
    "started_at": (TS, True, None),
    "finished_at": (TS, True, None),
    "mode_a_key": ("text", True, None),
    "mode_a_state": ("text", True, None),
    "created_at": (TS, False, NOW),
    "updated_at": (TS, False, NOW),
}

INDEXES = {
    "ix_projects_user_id_created_at",
    "ix_projects_status",
    "ix_projects_last_activity_at",
    "ix_songs_sha256",
    "ix_jobs_project_id_stage",
    "ix_jobs_state",
    "ix_clip_candidates_project_id_status",
    "ix_edit_plans_content_hash",
    "ix_renders_project_id",
}  # + pk/uq indexes; the notice counts the 3 + 1 + 2 secondary indexes and the unique ones below
CONSTRAINTS = {
    "pk_users", "uq_users_email",
    "pk_projects", "fk_projects_user_id_users", "ck_projects_status", "ck_projects_manual_retries",
    "pk_songs", "fk_songs_project_id_projects", "uq_songs_project_id", "ck_songs_size_bytes",
    "ck_songs_sha256_len",
    "pk_jobs", "fk_jobs_project_id_projects", "ck_jobs_stage", "ck_jobs_queue", "ck_jobs_state",
    "fk_jobs_render_id_renders",
    "pk_analyses", "fk_analyses_song_id_songs", "uq_analyses_song_id",
    "ck_analyses_beat_confidence", "ck_analyses_fallback",
    "pk_clip_candidates", "fk_clip_candidates_project_id_projects", "uq_clip_candidates_project_id",
    "ck_clip_candidates_provider", "ck_clip_candidates_status", "ck_clip_candidates_mezz_frames",
    "pk_edit_plans", "fk_edit_plans_project_id_projects", "uq_edit_plans_project_id",
    "ck_edit_plans_version", "ck_edit_plans_created_by", "ck_edit_plans_content_hash_len",
    "pk_renders", "fk_renders_project_id_projects", "fk_renders_edit_plan_id_edit_plans",
    "fk_renders_user_id_users", "ck_renders_state", "ck_renders_mode_a_state",
    "ck_renders_job_hash_len",
}  # fmt: skip
TABLES = {
    "alembic_version", "users", "projects", "songs", "jobs",
    "analyses", "clip_candidates", "edit_plans", "renders",
}  # fmt: skip


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
                " AND (indexname LIKE 'ix\\_%'"
                " OR indexname IN ('uq_jobs_active', 'uq_renders_job_hash'))"
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
    assert set(snap["indexes"]) == INDEXES | {"uq_jobs_active", "uq_renders_job_hash"}
    assert snap["constraints"] == CONSTRAINTS
    ix = snap["indexes"]
    assert "created_at DESC" in ix["ix_projects_user_id_created_at"]
    assert "WHERE (status <> 'deleted'::text)" in ix["ix_projects_status"]
    assert "WHERE (intermediates_purged_at IS NULL)" in ix["ix_projects_last_activity_at"]
    assert "WHERE (state = ANY (ARRAY['queued'::text, 'running'::text]))" in ix["ix_jobs_state"]
    assert (
        "UNIQUE INDEX uq_jobs_active ON public.jobs USING btree (project_id)"
        in (ix["uq_jobs_active"])
    )
    assert (
        "'draft'::text, 'replan'::text, 'rehydrate'::text, 'render'::text, 'remux'::text"
        in (ix["uq_jobs_active"])
    )
    assert "UNIQUE INDEX uq_renders_job_hash" in ix["uq_renders_job_hash"]
    assert (
        "'queued'::text, 'running'::text, 'verifying'::text, 'ready'::text"
        in (ix["uq_renders_job_hash"])
    )


async def test_owner_row_is_seeded_once(migrated_db: Db) -> None:
    again = migrated_db.alembic("upgrade", "head")
    assert again.returncode == 0, again.stderr
    conn = await asyncpg.connect(migrated_db.raw("postgres"))
    try:
        rows = await conn.fetch("SELECT id::text, email, display_name FROM users")
    finally:
        await conn.close()
    assert [tuple(r) for r in rows] == [(OWNER_ID, "owner@saveclock.local", OWNER_NAME)]


@pytest.mark.migration_roundtrip
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


@pytest.mark.migration_roundtrip
async def test_downgrade_one_step_roundtrip(migrated_db: Db) -> None:
    before = await snapshot(migrated_db)
    down = migrated_db.alembic("downgrade", "-1")
    assert down.returncode == 0, down.stderr
    up = migrated_db.alembic("upgrade", "head")
    assert up.returncode == 0, up.stderr
    assert await snapshot(migrated_db) == before


async def test_heads(migrated_db: Db) -> None:
    out = migrated_db.alembic("heads")
    assert out.stdout.strip() == "0002_analysis_pipeline (head)"


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
            "ck_analyses_fallback": {m.value for m in Fallback},
            "ck_clip_candidates_provider": {m.value for m in Provider},
            "ck_clip_candidates_status": {m.value for m in ClipStatus},
            "ck_edit_plans_created_by": {m.value for m in PlanCreator},
            "ck_renders_state": {m.value for m in RenderState},
            "ck_renders_mode_a_state": {m.value for m in ModeAState},
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


# --- behaviour of the 0002 constraints, through asyncpg as the superuser ---------------------

USER = "00000000-0000-4000-8000-000000000001"


async def _conn(db: Db, role: str = "postgres") -> asyncpg.Connection:
    return await asyncpg.connect(db.raw(role))


async def _project_and_song(conn: asyncpg.Connection) -> tuple[uuid.UUID, uuid.UUID]:
    pid, sid = uuid.uuid4(), uuid.uuid4()
    await conn.execute("INSERT INTO projects (id, user_id) VALUES ($1, $2)", pid, uuid.UUID(USER))
    await conn.execute(
        "INSERT INTO songs (id, project_id, original_filename, size_bytes, content_type)"
        " VALUES ($1, $2, 'a.wav', 1, 'audio/wav')",
        sid,
        pid,
    )
    return pid, sid


ANALYSIS_SQL = (
    "INSERT INTO analyses (id, song_id, model, model_version, tempo_bpm, beat_confidence,"
    " fallback, beat_map, sections, energy_curve, waveform_peaks)"
    " VALUES ($1, $2, 'beat_this', '1.1.0', 120, $3, $4, '{}', '[]', '[]', '[]')"
)


async def test_analyses_checks(migrated_db: Db) -> None:
    conn = await _conn(migrated_db)
    try:
        _, sid = await _project_and_song(conn)
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(ANALYSIS_SQL, uuid.uuid4(), sid, 1.5, None)
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(ANALYSIS_SQL, uuid.uuid4(), sid, 0.5, "nope")
        await conn.execute(ANALYSIS_SQL, uuid.uuid4(), sid, 0.5, "energy_grid")
        with pytest.raises(asyncpg.UniqueViolationError):  # one analysis per song
            await conn.execute(ANALYSIS_SQL, uuid.uuid4(), sid, 0.5, None)
    finally:
        await conn.close()


EDIT_PLAN_SQL = (
    "INSERT INTO edit_plans (id, project_id, version, schema_version, plan, content_hash,"
    " created_by) VALUES ($1, $2, $3, '1.0', '{}', $4, 'planner')"
)


async def test_edit_plan_version_and_hash_rules(migrated_db: Db) -> None:
    conn = await _conn(migrated_db)
    try:
        pid, _ = await _project_and_song(conn)
        await conn.execute(EDIT_PLAN_SQL, uuid.uuid4(), pid, 1, b"x" * 32)
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(EDIT_PLAN_SQL, uuid.uuid4(), pid, 1, b"y" * 32)
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(EDIT_PLAN_SQL, uuid.uuid4(), pid, 2, b"short")
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(EDIT_PLAN_SQL, uuid.uuid4(), pid, 0, b"x" * 32)
    finally:
        await conn.close()


RENDER_SQL = (
    "INSERT INTO renders (id, project_id, edit_plan_id, user_id, job_hash, state)"
    " VALUES ($1, $2, $3, $4, $5, $6)"
)


async def test_render_job_hash_is_unique_only_while_active(migrated_db: Db) -> None:
    conn = await _conn(migrated_db)
    try:
        pid, _ = await _project_and_song(conn)
        plan_id = uuid.uuid4()
        await conn.execute(EDIT_PLAN_SQL, plan_id, pid, 1, b"x" * 32)
        owner = uuid.UUID(USER)
        first = uuid.uuid4()
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(RENDER_SQL, uuid.uuid4(), pid, plan_id, owner, b"h" * 31, "queued")
        await conn.execute(RENDER_SQL, first, pid, plan_id, owner, b"h" * 32, "queued")
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(RENDER_SQL, uuid.uuid4(), pid, plan_id, owner, b"h" * 32, "queued")
        await conn.execute("UPDATE renders SET state = 'failed' WHERE id = $1", first)
        await conn.execute(RENDER_SQL, uuid.uuid4(), pid, plan_id, owner, b"h" * 32, "queued")
    finally:
        await conn.close()


async def _job(conn: asyncpg.Connection, pid: uuid.UUID, stage: str, state: str) -> None:
    await conn.execute(
        "INSERT INTO jobs (id, project_id, stage, queue, state) VALUES ($1, $2, $3, 'fetch', $4)",
        uuid.uuid4(),
        pid,
        stage,
        state,
    )


async def test_one_active_plan_changing_job_per_project(migrated_db: Db) -> None:
    conn = await _conn(migrated_db)
    try:
        pid, _ = await _project_and_song(conn)
        other, _ = await _project_and_song(conn)
        await _job(conn, pid, "draft", "queued")
        with pytest.raises(asyncpg.UniqueViolationError):
            await _job(conn, pid, "draft", "queued")
        with pytest.raises(asyncpg.UniqueViolationError):
            await _job(conn, pid, "render", "running")
        for stage in ("validate", "analyze", "swap_normalize"):  # not covered by the index
            await _job(conn, pid, stage, "running")
        await _job(conn, other, "draft", "queued")  # another project is independent
        await conn.execute(
            "UPDATE jobs SET state = 'ok' WHERE project_id = $1 AND stage = 'draft'", pid
        )
        await _job(conn, pid, "render", "queued")  # a finished job frees the slot
    finally:
        await conn.close()


async def test_deleting_a_project_cascades_to_the_new_tables(migrated_db: Db) -> None:
    conn = await _conn(migrated_db)
    try:
        pid, sid = await _project_and_song(conn)
        plan_id, render_id = uuid.uuid4(), uuid.uuid4()
        await conn.execute(ANALYSIS_SQL, uuid.uuid4(), sid, 0.5, None)
        await conn.execute(EDIT_PLAN_SQL, plan_id, pid, 1, b"x" * 32)
        await conn.execute(RENDER_SQL, render_id, pid, plan_id, uuid.UUID(USER), b"h" * 32, "ready")
        await conn.execute(
            "INSERT INTO clip_candidates (id, project_id, provider, provider_id, query, page_url,"
            " license) VALUES ($1, $2, 'pexels', '1', 'q', 'u', 'l')",
            uuid.uuid4(),
            pid,
        )
        await conn.execute(
            "INSERT INTO jobs (id, project_id, render_id, stage, queue)"
            " VALUES ($1, $2, $3, 'render', 'render')",
            uuid.uuid4(),
            pid,
            render_id,
        )
        await conn.execute("DELETE FROM projects WHERE id = $1", pid)
        for table in ("analyses", "clip_candidates", "edit_plans", "renders", "jobs"):
            assert await conn.fetchval(f"SELECT count(*) FROM {table}") == 0, table  # noqa: S608
    finally:
        await conn.close()


async def test_deleting_a_render_keeps_the_job_history(migrated_db: Db) -> None:
    conn = await _conn(migrated_db)
    try:
        pid, _ = await _project_and_song(conn)
        plan_id, render_id, job_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        await conn.execute(EDIT_PLAN_SQL, plan_id, pid, 1, b"x" * 32)
        await conn.execute(RENDER_SQL, render_id, pid, plan_id, uuid.UUID(USER), b"h" * 32, "ready")
        await conn.execute(
            "INSERT INTO jobs (id, project_id, render_id, stage, queue, state)"
            " VALUES ($1, $2, $3, 'render', 'render', 'ok')",
            job_id,
            pid,
            render_id,
        )
        await conn.execute("DELETE FROM renders WHERE id = $1", render_id)
        row = await conn.fetchrow("SELECT project_id, render_id FROM jobs WHERE id = $1", job_id)
        assert row is not None
        assert row["project_id"] == pid
        assert row["render_id"] is None
    finally:
        await conn.close()


async def test_app_role_can_use_the_new_tables_but_not_alter_them(migrated_db: Db) -> None:
    setup = await _conn(migrated_db)
    try:
        _, sid = await _project_and_song(setup)
    finally:
        await setup.close()
    app = await _conn(migrated_db, "app_rw")
    try:
        await app.execute(ANALYSIS_SQL, uuid.uuid4(), sid, 0.5, None)
        assert await app.fetchval("SELECT count(*) FROM analyses") == 1
        for table in ("analyses", "clip_candidates", "edit_plans", "renders"):
            await app.fetch(f"SELECT 1 FROM {table}")  # noqa: S608
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app.execute("DROP TABLE analyses")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app.execute("CREATE TABLE z (i int)")
    finally:
        await app.close()

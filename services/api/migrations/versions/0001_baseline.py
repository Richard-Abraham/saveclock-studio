"""Baseline: users, projects, songs, jobs and the seeded owner row.

Revision ID: 0001_baseline
Revises:
"""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

OWNER_ID = "00000000-0000-4000-8000-000000000001"
JSONB_EMPTY = sa.text("'{}'::jsonb")
NOW = sa.text("now()")


def _ts(name: str) -> sa.Column[datetime]:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=NOW)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("settings", postgresql.JSONB(), nullable=False, server_default=JSONB_EMPTY),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="created"),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("flags", postgresql.JSONB(), nullable=False, server_default=JSONB_EMPTY),
        sa.Column("options", postgresql.JSONB(), nullable=False, server_default=JSONB_EMPTY),
        sa.Column("upload_completed_at", sa.DateTime(timezone=True), nullable=True),
        _ts("last_activity_at"),
        sa.Column("intermediates_purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("manual_retries", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_projects_user_id_users")),
        sa.CheckConstraint(
            "status IN ('created','uploading','validating','analyzing','planning','draft_ready',"
            "'rendering','ready','failed_analysis','failed_plan','failed_render','rejected',"
            "'canceled','deleted')",
            name=op.f("ck_projects_status"),
        ),
        sa.CheckConstraint("manual_retries >= 0", name=op.f("ck_projects_manual_retries")),
    )
    op.create_index(
        op.f("ix_projects_user_id_created_at"),
        "projects",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        op.f("ix_projects_status"),
        "projects",
        ["status"],
        postgresql_where=sa.text("status <> 'deleted'"),
    )
    op.create_index(
        op.f("ix_projects_last_activity_at"),
        "projects",
        ["last_activity_at"],
        postgresql_where=sa.text("intermediates_purged_at IS NULL"),
    )
    op.create_table(
        "songs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("duration_s", sa.Numeric(8, 3), nullable=True),
        sa.Column("codec", sa.Text(), nullable=True),
        sa.Column("sample_rate", sa.Integer(), nullable=True),
        sa.Column("channels", sa.SmallInteger(), nullable=True),
        sa.Column("sha256", sa.LargeBinary(), nullable=True),
        sa.Column("source_ext", sa.Text(), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_songs")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_songs_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("project_id", name=op.f("uq_songs_project_id")),
        sa.CheckConstraint("size_bytes >= 0", name=op.f("ck_songs_size_bytes")),
        sa.CheckConstraint(
            "sha256 IS NULL OR octet_length(sha256) = 32", name=op.f("ck_songs_sha256_len")
        ),
    )
    op.create_index(op.f("ix_songs_sha256"), "songs", ["sha256"])
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("render_id", sa.Uuid(), nullable=True),  # FK to renders arrives in 0002
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("queue", sa.Text(), nullable=False),
        sa.Column("attempt", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("state", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timings", postgresql.JSONB(), nullable=False, server_default=JSONB_EMPTY),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_jobs_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "stage IN ('validate','analyze','draft','replan','rehydrate','swap_normalize',"
            "'render','remux','sweep','purge')",
            name=op.f("ck_jobs_stage"),
        ),
        sa.CheckConstraint(
            "queue IN ('analysis','fetch','render','maintenance')", name=op.f("ck_jobs_queue")
        ),
        sa.CheckConstraint(
            "state IN ('queued','running','ok','error','dead')", name=op.f("ck_jobs_state")
        ),
    )
    op.create_index(op.f("ix_jobs_project_id_stage"), "jobs", ["project_id", "stage"])
    op.create_index(
        op.f("ix_jobs_state"),
        "jobs",
        ["state"],
        postgresql_where=sa.text("state IN ('queued','running')"),
    )
    # data step: the single owner row (idempotent)
    attrs = context.config.attributes
    op.execute(
        sa.text(
            "INSERT INTO users (id, email, display_name, settings) "
            "VALUES (:id, :email, :name, '{}'::jsonb) ON CONFLICT (id) DO NOTHING"
        ).bindparams(
            sa.bindparam("id", UUID(OWNER_ID), type_=sa.Uuid()),
            sa.bindparam("email", attrs["owner_email"], type_=sa.Text()),
            sa.bindparam("name", attrs["owner_display_name"], type_=sa.Text()),
        )
    )


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_table("songs")
    op.drop_table("projects")
    op.drop_table("users")

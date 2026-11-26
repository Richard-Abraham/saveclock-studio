"""Analysis pipeline: four new tables, jobs.render_id FK and the uq_jobs_active index.

Revision ID: 0002_analysis_pipeline
Revises: 0001_baseline
"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_analysis_pipeline"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

JSONB_EMPTY = sa.text("'{}'::jsonb")
JSONB_EMPTY_LIST = sa.text("'[]'::jsonb")
NOW = sa.text("now()")


def _ts(name: str) -> sa.Column[datetime]:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=NOW)


def upgrade() -> None:
    op.create_table(
        "analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("song_id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("tempo_bpm", sa.Numeric(6, 2), nullable=False),
        sa.Column(
            "tempo_octave_adjust", sa.SmallInteger(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("beat_confidence", sa.REAL(), nullable=False),
        sa.Column("fallback", sa.Text(), nullable=True),
        sa.Column("beat_map", postgresql.JSONB(), nullable=False),
        sa.Column("sections", postgresql.JSONB(), nullable=False),
        sa.Column("energy_curve", postgresql.JSONB(), nullable=False),
        sa.Column("waveform_peaks", postgresql.JSONB(), nullable=False),
        sa.Column(
            "low_confidence_ranges",
            postgresql.JSONB(),
            nullable=False,
            server_default=JSONB_EMPTY_LIST,
        ),
        sa.Column("timing", postgresql.JSONB(), nullable=False, server_default=JSONB_EMPTY),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analyses")),
        sa.ForeignKeyConstraint(
            ["song_id"],
            ["songs.id"],
            name=op.f("fk_analyses_song_id_songs"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("song_id", name=op.f("uq_analyses_song_id")),
        sa.CheckConstraint(
            "beat_confidence >= 0 AND beat_confidence <= 1",
            name=op.f("ck_analyses_beat_confidence"),
        ),
        sa.CheckConstraint(
            "fallback IS NULL OR fallback IN ('energy_grid','even_grid','phrase_only')",
            name=op.f("ck_analyses_fallback"),
        ),
    )
    op.create_table(
        "clip_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("page_url", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("author_url", sa.Text(), nullable=True),
        sa.Column("license", sa.Text(), nullable=False),
        _ts("fetched_at"),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_s", sa.Numeric(7, 3), nullable=True),
        sa.Column("fps", sa.REAL(), nullable=True),
        sa.Column("download_url", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="found"),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("score", sa.REAL(), nullable=True),
        sa.Column("frame_scores", postgresql.JSONB(), nullable=True),
        sa.Column("window_start_s", sa.Numeric(7, 3), nullable=True),  # added by plan 004
        sa.Column("mezz_frames", sa.Integer(), nullable=True),  # added by plan 004
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clip_candidates")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_clip_candidates_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "project_id", "provider", "provider_id", name=op.f("uq_clip_candidates_project_id")
        ),
        sa.CheckConstraint(
            "provider IN ('pexels','pixabay')", name=op.f("ck_clip_candidates_provider")
        ),
        sa.CheckConstraint(
            "status IN ('found','downloaded','rejected_cut','rejected_quality','ranked',"
            "'normalized','selected')",
            name=op.f("ck_clip_candidates_status"),
        ),
        sa.CheckConstraint(
            "mezz_frames IS NULL OR mezz_frames > 0", name=op.f("ck_clip_candidates_mezz_frames")
        ),
    )
    op.create_index(
        op.f("ix_clip_candidates_project_id_status"),
        "clip_candidates",
        ["project_id", "status"],
    )
    op.create_table(
        "edit_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("plan", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.LargeBinary(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_edit_plans")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_edit_plans_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("project_id", "version", name=op.f("uq_edit_plans_project_id")),
        sa.CheckConstraint("version >= 1", name=op.f("ck_edit_plans_version")),
        sa.CheckConstraint(
            "created_by IN ('planner','user')", name=op.f("ck_edit_plans_created_by")
        ),
        sa.CheckConstraint(
            "octet_length(content_hash) = 32", name=op.f("ck_edit_plans_content_hash_len")
        ),
    )
    op.create_index(op.f("ix_edit_plans_content_hash"), "edit_plans", ["content_hash"])
    op.create_table(
        "renders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("edit_plan_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("job_hash", sa.LargeBinary(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("attempt", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("duration_frames", sa.Integer(), nullable=True),
        sa.Column("verify", postgresql.JSONB(), nullable=False, server_default=JSONB_EMPTY),
        sa.Column("render_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mode_a_key", sa.Text(), nullable=True),
        sa.Column("mode_a_state", sa.Text(), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_renders")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_renders_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["edit_plan_id"], ["edit_plans.id"], name=op.f("fk_renders_edit_plan_id_edit_plans")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_renders_user_id_users")),
        sa.CheckConstraint(
            "state IN ('queued','running','verifying','ready','failed','canceled')",
            name=op.f("ck_renders_state"),
        ),
        sa.CheckConstraint(
            "mode_a_state IS NULL OR mode_a_state IN ('queued','running','ready','failed')",
            name=op.f("ck_renders_mode_a_state"),
        ),
        sa.CheckConstraint("octet_length(job_hash) = 32", name=op.f("ck_renders_job_hash_len")),
    )
    op.create_index(
        "uq_renders_job_hash",
        "renders",
        ["job_hash"],
        unique=True,
        postgresql_where=sa.text("state IN ('queued','running','verifying','ready')"),
    )
    op.create_index(op.f("ix_renders_project_id"), "renders", ["project_id"])
    op.create_foreign_key(
        op.f("fk_jobs_render_id_renders"),
        "jobs",
        "renders",
        ["render_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_jobs_active",
        "jobs",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text(
            "state IN ('queued','running') "
            "AND stage IN ('draft','replan','rehydrate','render','remux')"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_jobs_active", table_name="jobs")
    op.drop_constraint(op.f("fk_jobs_render_id_renders"), "jobs", type_="foreignkey")
    op.drop_table("renders")
    op.drop_table("edit_plans")
    op.drop_table("clip_candidates")
    op.drop_table("analyses")

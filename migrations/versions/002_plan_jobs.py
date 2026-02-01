from __future__ import annotations

import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_plan_jobs"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meta", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_plans_status_updated", "plans", ["status", sa.text("updated_at DESC")])

    default_plan_id = uuid.uuid4()
    op.execute(
        sa.text(
            "INSERT INTO plans (id, name, status, created_at, updated_at, meta) "
            "VALUES (:id, 'default', 'active', NOW(), NOW(), '{}')"
        ).bindparams(id=default_plan_id)
    )

    op.add_column("threads", sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(sa.text("UPDATE threads SET plan_id = :id").bindparams(id=default_plan_id))
    op.alter_column("threads", "plan_id", nullable=False)
    op.create_foreign_key("fk_threads_plan", "threads", "plans", ["plan_id"], ["id"], ondelete="CASCADE")

    op.add_column("turns", sa.Column("external_turn_id", sa.String(), nullable=True))
    op.create_index(
        "uq_turns_external_id",
        "turns",
        ["thread_id", "external_turn_id"],
        unique=True,
    )

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_jobs_status_run", "jobs", ["status", "run_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_status_run", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("uq_turns_external_id", table_name="turns")
    op.drop_column("turns", "external_turn_id")
    op.drop_constraint("fk_threads_plan", "threads", type_="foreignkey")
    op.drop_column("threads", "plan_id")
    op.drop_index("ix_plans_status_updated", table_name="plans")
    op.drop_table("plans")

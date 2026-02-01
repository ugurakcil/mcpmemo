from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meta", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meta", postgresql.JSONB(), nullable=False),
        sa.Column("branch_id", sa.String(), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', coalesce(text, ''))", persisted=True),
        ),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_turns_thread_ts", "turns", ["thread_id", sa.text("ts DESC")])
    op.create_index("ix_turns_tsv", "turns", ["tsv"], postgresql_using="gin")
    op.create_index("ix_turns_embedding", "turns", ["embedding"], postgresql_using="ivfflat")

    op.create_table(
        "memory_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("severity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("affects", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("code_refs", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("evidence_turn_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("superseded_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("supersede_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(statement, ''))",
                persisted=True,
            ),
        ),
        sa.Column("meta", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("importance >= 0 AND importance <= 1", name="ck_importance_range"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_confidence_range"),
        sa.CheckConstraint("severity >= 0 AND severity <= 1", name="ck_severity_range"),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["memory_items.id"]),
        sa.ForeignKeyConstraint(["superseded_by_id"], ["memory_items.id"]),
    )
    op.create_index("ix_memory_thread_type_status", "memory_items", ["thread_id", "type", "status"])
    op.create_index(
        "ix_memory_thread_status_importance_updated",
        "memory_items",
        ["thread_id", "status", sa.text("importance DESC"), sa.text("updated_at DESC")],
    )
    op.create_index("ix_memory_tags", "memory_items", ["tags"], postgresql_using="gin")
    op.create_index("ix_memory_affects", "memory_items", ["affects"], postgresql_using="gin")
    op.create_index("ix_memory_tsv", "memory_items", ["tsv"], postgresql_using="gin")
    op.create_index("ix_memory_embedding", "memory_items", ["embedding"], postgresql_using="ivfflat")

    op.create_table(
        "shared_packages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("signature", sa.String(), nullable=False),
        sa.Column("meta", postgresql.JSONB(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("shared_packages")
    op.drop_index("ix_memory_embedding", table_name="memory_items")
    op.drop_index("ix_memory_tsv", table_name="memory_items")
    op.drop_index("ix_memory_affects", table_name="memory_items")
    op.drop_index("ix_memory_tags", table_name="memory_items")
    op.drop_index("ix_memory_thread_status_importance_updated", table_name="memory_items")
    op.drop_index("ix_memory_thread_type_status", table_name="memory_items")
    op.drop_table("memory_items")
    op.drop_index("ix_turns_embedding", table_name="turns")
    op.drop_index("ix_turns_tsv", table_name="turns")
    op.drop_index("ix_turns_thread_ts", table_name="turns")
    op.drop_table("turns")
    op.drop_table("threads")

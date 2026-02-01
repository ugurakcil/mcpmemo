from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    ARRAY,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import Computed

from memory_mcp.config import settings

Base = declarative_base()


class Thread(Base):
    __tablename__ = "threads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    meta = Column(JSON, default=dict, nullable=False)


class Turn(Base):
    __tablename__ = "turns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    ts = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    meta = Column(JSON, default=dict, nullable=False)
    branch_id = Column(String, nullable=True)
    external_turn_id = Column(String, nullable=True)
    embedding = Column(Vector(settings.embedding_dim), nullable=True)
    tsv = Column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(text, ''))", persisted=True),
    )

    __table_args__ = (
        UniqueConstraint("thread_id", "external_turn_id", name="uq_turns_external_id"),
    )


Index("ix_turns_thread_ts", Turn.thread_id, Turn.ts.desc())
Index("ix_turns_tsv", Turn.tsv, postgresql_using="gin")
Index("ix_turns_embedding", Turn.embedding, postgresql_using="ivfflat")


class MemoryItem(Base):
    __tablename__ = "memory_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    title = Column(String, nullable=False)
    statement = Column(Text, nullable=False)
    importance = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    severity = Column(Float, nullable=False, default=0.0)
    tags = Column(ARRAY(String), nullable=False, default=list)
    affects = Column(ARRAY(String), nullable=False, default=list)
    code_refs = Column(ARRAY(String), nullable=False, default=list)
    evidence_turn_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    supersedes_id = Column(UUID(as_uuid=True), ForeignKey("memory_items.id"), nullable=True)
    superseded_by_id = Column(UUID(as_uuid=True), ForeignKey("memory_items.id"), nullable=True)
    supersede_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    embedding = Column(Vector(settings.embedding_dim), nullable=True)
    tsv = Column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(statement, ''))",
            persisted=True,
        ),
    )
    meta = Column(JSON, default=dict, nullable=False)

    __table_args__ = (
        CheckConstraint("importance >= 0 AND importance <= 1", name="ck_importance_range"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_confidence_range"),
        CheckConstraint("severity >= 0 AND severity <= 1", name="ck_severity_range"),
    )


Index("ix_memory_thread_type_status", MemoryItem.thread_id, MemoryItem.type, MemoryItem.status)
Index(
    "ix_memory_thread_status_importance_updated",
    MemoryItem.thread_id,
    MemoryItem.status,
    MemoryItem.importance.desc(),
    MemoryItem.updated_at.desc(),
)
Index("ix_memory_tags", MemoryItem.tags, postgresql_using="gin")
Index("ix_memory_affects", MemoryItem.affects, postgresql_using="gin")
Index("ix_memory_tsv", MemoryItem.tsv, postgresql_using="gin")
Index("ix_memory_embedding", MemoryItem.embedding, postgresql_using="ivfflat")


class SharedPackage(Base):
    __tablename__ = "shared_packages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    payload = Column(JSON, nullable=False)
    signature = Column(String, nullable=False)
    meta = Column(JSON, default=dict, nullable=False)


class Plan(Base):
    __tablename__ = "plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    meta = Column(JSON, default=dict, nullable=False)


Index("ix_plans_status_updated", Plan.status, Plan.updated_at.desc())


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    payload = Column(JSON, nullable=False)
    run_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


Index("ix_jobs_status_run", Job.status, Job.run_at)

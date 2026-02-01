from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    decision = "decision"
    constraint = "constraint"
    mistake = "mistake"
    assumption = "assumption"
    open_question = "open_question"


class MemoryStatus(str, Enum):
    active = "active"
    deprecated = "deprecated"
    superseded = "superseded"


class RetrievalMode(str, Enum):
    fast = "fast"
    deep = "deep"


class RetrievalScope(str, Enum):
    distilled_only = "distilled_only"
    raw_only = "raw_only"
    hybrid = "hybrid"


class ThreadCreateResponse(BaseModel):
    thread_id: UUID


class ThreadCreateRequest(BaseModel):
    plan_id: UUID
    meta: dict[str, Any] = Field(default_factory=dict)


class TurnIngestRequest(BaseModel):
    thread_id: UUID
    role: str
    text: str
    ts: Optional[datetime] = None
    meta: dict[str, Any] = Field(default_factory=dict)
    branch_id: Optional[str] = None
    external_turn_id: Optional[str] = None
    embed_now: bool = False


class TurnIngestResponse(BaseModel):
    turn_id: UUID


class DistillExtractRequest(BaseModel):
    thread_id: UUID
    turn_id: UUID
    include_recent_turns: int = 4
    write_to_memory: bool = True


class DistillItem(BaseModel):
    title: str
    statement: str
    importance: float
    confidence: float
    severity: float = 0.0
    tags: List[str] = Field(default_factory=list)
    affects: List[str] = Field(default_factory=list)
    code_refs: List[str] = Field(default_factory=list)


class DistillResult(BaseModel):
    decisions: List[DistillItem] = Field(default_factory=list)
    constraints: List[DistillItem] = Field(default_factory=list)
    mistakes: List[DistillItem] = Field(default_factory=list)
    assumptions: List[DistillItem] = Field(default_factory=list)
    open_questions: List[DistillItem] = Field(default_factory=list)


class DistillExtractResponse(BaseModel):
    inserted: int
    deduped: int
    superseded: int
    extracted: DistillResult


class MemoryUpsertRequest(BaseModel):
    thread_id: UUID
    type: MemoryType
    title: str
    statement: str
    importance: float
    confidence: float
    severity: float = 0.0
    tags: List[str] = Field(default_factory=list)
    affects: List[str] = Field(default_factory=list)
    code_refs: List[str] = Field(default_factory=list)
    evidence_turn_ids: List[UUID] = Field(default_factory=list)


class MemoryUpsertResponse(BaseModel):
    id: UUID
    status: MemoryStatus


class MemoryDeprecateRequest(BaseModel):
    item_id: UUID
    reason: str


class MemorySupersedeRequest(BaseModel):
    old_item_id: UUID
    new_item: MemoryUpsertRequest
    reason: str


class ScoreOverrideRequest(BaseModel):
    item_id: UUID
    importance: Optional[float] = None
    confidence: Optional[float] = None
    severity: Optional[float] = None
    reason: str


class RetrieveDecisionStateResponse(BaseModel):
    decisions: List[dict[str, Any]]
    constraints: List[dict[str, Any]]
    avoid_list_mistakes: List[dict[str, Any]]
    assumptions: List[dict[str, Any]]
    open_questions: List[dict[str, Any]]


class RetrieveDecisionStateRequest(BaseModel):
    thread_id: UUID


class RetrieveContextRequest(BaseModel):
    thread_id: UUID
    query: str
    mode: RetrievalMode = RetrievalMode.fast
    scope: RetrievalScope = RetrievalScope.distilled_only
    top_k: int = 8
    token_budget: int = 800
    recency_bias: float = 0.1
    explain: bool = False


class RetrieveContextChunk(BaseModel):
    source: str
    item_id: UUID | None
    text: str
    score: float
    score_detail: dict[str, Any] | None = None


class RetrieveContextResponse(BaseModel):
    chunks: List[RetrieveContextChunk]
    est_tokens: int
    low_confidence: bool
    debug_scores: dict[str, Any]
    stale_references: List[str]


class AuditCheckRequest(BaseModel):
    thread_id: UUID
    proposed_plan_text: str
    deep: bool = False


class AuditCheckResponse(BaseModel):
    violations: List[str]
    stale_references: List[str]
    missing_constraints: List[str]
    fixes: List[str]


class PlanCreateRequest(BaseModel):
    name: str
    meta: dict[str, Any] = Field(default_factory=dict)


class PlanCreateResponse(BaseModel):
    plan_id: UUID


class PlanListRequest(BaseModel):
    include_archived: bool = False


class PlanListResponse(BaseModel):
    plans: List[dict[str, Any]]


class PlanGetRequest(BaseModel):
    plan_id: UUID


class PlanRenameRequest(BaseModel):
    plan_id: UUID
    name: str


class PlanArchiveRequest(BaseModel):
    plan_id: UUID
    archived: bool = True


class PlanTouchRequest(BaseModel):
    plan_id: UUID


class SharedExportRequest(BaseModel):
    thread_id: UUID
    types: List[MemoryType] = Field(default_factory=lambda: [MemoryType.decision, MemoryType.constraint])
    include_mistakes: bool = False
    expires_in_minutes: int = 60


class SharedExportResponse(BaseModel):
    package_id: UUID
    payload: dict[str, Any]
    signature: str


class SharedImportRequest(BaseModel):
    payload: dict[str, Any]
    signature: str


class SharedImportResponse(BaseModel):
    imported_count: int
    thread_id_created: UUID
    items: List[dict[str, Any]]

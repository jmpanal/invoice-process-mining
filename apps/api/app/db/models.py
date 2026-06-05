from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

try:
    from pgvector.sqlalchemy import Vector

    EmbeddingType = Vector(1536).with_variant(JSON, "sqlite")
except Exception:
    EmbeddingType = JSON


def uuid_str() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class IdealProcess(Base, TimestampMixin):
    __tablename__ = "ideal_processes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, default="1.0", nullable=False)
    canonical_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    bpmn_xml: Mapped[str] = mapped_column(Text, default="", nullable=False)

    nodes: Mapped[list["IdealProcessNode"]] = relationship(back_populates="process", cascade="all, delete-orphan")
    edges: Mapped[list["IdealProcessEdge"]] = relationship(back_populates="process", cascade="all, delete-orphan")


class IdealProcessNode(Base, TimestampMixin):
    __tablename__ = "ideal_process_nodes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    process_id: Mapped[str] = mapped_column(ForeignKey("ideal_processes.id"), nullable=False)
    node_key: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    node_type: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    system: Mapped[str] = mapped_column(String, nullable=False)
    is_control_point: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    node_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    process: Mapped[IdealProcess] = relationship(back_populates="nodes")

    __table_args__ = (Index("ix_ideal_process_nodes_process_id", "process_id"),)


class IdealProcessEdge(Base, TimestampMixin):
    __tablename__ = "ideal_process_edges"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    process_id: Mapped[str] = mapped_column(ForeignKey("ideal_processes.id"), nullable=False)
    source_node_key: Mapped[str] = mapped_column(String, nullable=False)
    target_node_key: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, default="", nullable=False)
    edge_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    process: Mapped[IdealProcess] = relationship(back_populates="edges")

    __table_args__ = (Index("ix_ideal_process_edges_process_id", "process_id"),)


class UploadedEventLog(Base, TimestampMixin):
    __tablename__ = "uploaded_event_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, default="generated", nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    case_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hidden_step_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    date_start: Mapped[datetime | None] = mapped_column(DateTime)
    date_end: Mapped[datetime | None] = mapped_column(DateTime)
    csv_path: Mapped[str] = mapped_column(String, default="", nullable=False)
    log_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    events: Mapped[list["ProcessEvent"]] = relationship(back_populates="event_log", cascade="all, delete-orphan")


class ProcessEvent(Base, TimestampMixin):
    __tablename__ = "process_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    event_log_id: Mapped[str] = mapped_column(ForeignKey("uploaded_event_logs.id"), nullable=False)
    case_id: Mapped[str] = mapped_column(String, nullable=False)
    invoice_id: Mapped[str] = mapped_column(String, nullable=False)
    activity: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    system: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    invoice_amount: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String, default="EUR", nullable=False)
    country: Mapped[str] = mapped_column(String, default="DE", nullable=False)
    vendor_id: Mapped[str] = mapped_column(String, nullable=False)
    vendor_risk: Mapped[str] = mapped_column(String, nullable=False)
    po_number: Mapped[str] = mapped_column(String, default="", nullable=False)
    exception_type: Mapped[str] = mapped_column(String, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, default="", nullable=False)
    is_hidden_step: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hidden_issue_type: Mapped[str] = mapped_column(String, default="", nullable=False)

    event_log: Mapped[UploadedEventLog] = relationship(back_populates="events")

    __table_args__ = (Index("ix_process_events_event_log_id", "event_log_id"),)


class MiningRun(Base, TimestampMixin):
    __tablename__ = "mining_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    ideal_process_id: Mapped[str] = mapped_column(ForeignKey("ideal_processes.id"), nullable=False)
    event_log_id: Mapped[str] = mapped_column(ForeignKey("uploaded_event_logs.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="completed", nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    top_variants: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    top_hidden_issues: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    top_bottlenecks: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    nodes: Mapped[list["MinedNode"]] = relationship(cascade="all, delete-orphan")
    edges: Mapped[list["MinedEdge"]] = relationship(cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_mining_runs_event_log_id", "event_log_id"),
        Index("ix_mining_runs_ideal_process_id", "ideal_process_id"),
    )


class MinedNode(Base, TimestampMixin):
    __tablename__ = "mined_nodes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    mining_run_id: Mapped[str] = mapped_column(ForeignKey("mining_runs.id"), nullable=False)
    activity: Mapped[str] = mapped_column(String, nullable=False)
    frequency: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_bottleneck: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    severity: Mapped[str] = mapped_column(String, default="normal", nullable=False)
    node_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (Index("ix_mined_nodes_mining_run_id", "mining_run_id"),)


class MinedEdge(Base, TimestampMixin):
    __tablename__ = "mined_edges"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    mining_run_id: Mapped[str] = mapped_column(ForeignKey("mining_runs.id"), nullable=False)
    source_activity: Mapped[str] = mapped_column(String, nullable=False)
    target_activity: Mapped[str] = mapped_column(String, nullable=False)
    frequency: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_wait_hours: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_bottleneck: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    severity: Mapped[str] = mapped_column(String, default="normal", nullable=False)
    edge_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (Index("ix_mined_edges_mining_run_id", "mining_run_id"),)


class DocumentChunk(Base, TimestampMixin):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    document_title: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_file_path: Mapped[str] = mapped_column(String, nullable=False)
    source_repository: Mapped[str] = mapped_column(String, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(EmbeddingType, nullable=False)
    chunk_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_document_chunks_source_type", "source_type"),
        Index("ix_document_chunks_source_file_path", "source_file_path"),
    )


class RagQuery(Base, TimestampMixin):
    __tablename__ = "rag_queries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    mining_run_id: Mapped[str | None] = mapped_column(String)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    retrieved_chunks: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    visible_trace: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class ImprovementProposal(Base, TimestampMixin):
    __tablename__ = "improvement_proposals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    mining_run_id: Mapped[str] = mapped_column(ForeignKey("mining_runs.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    expected_impact: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String, nullable=False)
    required_approvers: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    monitoring_kpis: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    proposal_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    actions: Mapped[list["ImprovementAction"]] = relationship(back_populates="proposal", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_improvement_proposals_mining_run_id", "mining_run_id"),)


class ImprovementAction(Base, TimestampMixin):
    __tablename__ = "improvement_actions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("improvement_proposals.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    target_system: Mapped[str] = mapped_column(String, nullable=False)
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    preconditions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    required_approvers: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    expected_config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    approval_status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    rejected_by: Mapped[str | None] = mapped_column(String)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime)
    approval_comment: Mapped[str | None] = mapped_column(Text)
    action_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    proposal: Mapped[ImprovementProposal] = relationship(back_populates="actions")

    __table_args__ = (
        Index("ix_improvement_actions_proposal_id", "proposal_id"),
        Index("ix_improvement_actions_approval_status", "approval_status"),
    )


class AgentRun(Base, TimestampMixin):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    action_id: Mapped[str] = mapped_column(ForeignKey("improvement_actions.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="running", nullable=False)
    validation_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    steps: Mapped[list["AgentStep"]] = relationship(back_populates="agent_run", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_agent_runs_action_id", "action_id"),)


class AgentStep(Base, TimestampMixin):
    __tablename__ = "agent_steps"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    agent_run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    input_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)

    agent_run: Mapped[AgentRun] = relationship(back_populates="steps")

    __table_args__ = (Index("ix_agent_steps_agent_run_id", "agent_run_id"),)


class MockSystemConfig(Base, TimestampMixin):
    __tablename__ = "mock_system_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    agent_run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False)
    action_id: Mapped[str] = mapped_column(ForeignKey("improvement_actions.id"), nullable=False)
    target_system: Mapped[str] = mapped_column(String, nullable=False)
    configuration_type: Mapped[str] = mapped_column(String, nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    validation_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_final_human_enablement: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (Index("ix_mock_system_configs_agent_run_id", "agent_run_id"),)

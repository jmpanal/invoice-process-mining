from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

try:
    from pgvector.sqlalchemy import Vector
except Exception:
    Vector = None

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def embedding_type():
    if Vector is not None:
        return Vector(1536)
    return json_type()


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "ideal_processes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("canonical_json", json_type(), nullable=False),
        sa.Column("bpmn_xml", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "ideal_process_nodes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("process_id", sa.String(), sa.ForeignKey("ideal_processes.id"), nullable=False),
        sa.Column("node_key", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("node_type", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("system", sa.String(), nullable=False),
        sa.Column("is_control_point", sa.Boolean(), nullable=False),
        sa.Column("node_metadata", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ideal_process_nodes_process_id", "ideal_process_nodes", ["process_id"])
    op.create_table(
        "ideal_process_edges",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("process_id", sa.String(), sa.ForeignKey("ideal_processes.id"), nullable=False),
        sa.Column("source_node_key", sa.String(), nullable=False),
        sa.Column("target_node_key", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("edge_metadata", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ideal_process_edges_process_id", "ideal_process_edges", ["process_id"])
    op.create_table(
        "uploaded_event_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("hidden_step_count", sa.Integer(), nullable=False),
        sa.Column("date_start", sa.DateTime()),
        sa.Column("date_end", sa.DateTime()),
        sa.Column("csv_path", sa.String(), nullable=False),
        sa.Column("log_metadata", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "process_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("event_log_id", sa.String(), sa.ForeignKey("uploaded_event_logs.id"), nullable=False),
        sa.Column("case_id", sa.String(), nullable=False),
        sa.Column("invoice_id", sa.String(), nullable=False),
        sa.Column("activity", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("system", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("invoice_amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("country", sa.String(), nullable=False),
        sa.Column("vendor_id", sa.String(), nullable=False),
        sa.Column("vendor_risk", sa.String(), nullable=False),
        sa.Column("po_number", sa.String(), nullable=False),
        sa.Column("exception_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("is_hidden_step", sa.Boolean(), nullable=False),
        sa.Column("hidden_issue_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_process_events_event_log_id", "process_events", ["event_log_id"])
    op.create_table(
        "mining_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("ideal_process_id", sa.String(), sa.ForeignKey("ideal_processes.id"), nullable=False),
        sa.Column("event_log_id", sa.String(), sa.ForeignKey("uploaded_event_logs.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("metrics", json_type(), nullable=False),
        sa.Column("top_variants", json_type(), nullable=False),
        sa.Column("top_hidden_issues", json_type(), nullable=False),
        sa.Column("top_bottlenecks", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_mining_runs_event_log_id", "mining_runs", ["event_log_id"])
    op.create_index("ix_mining_runs_ideal_process_id", "mining_runs", ["ideal_process_id"])
    op.create_table(
        "mined_nodes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("mining_run_id", sa.String(), sa.ForeignKey("mining_runs.id"), nullable=False),
        sa.Column("activity", sa.String(), nullable=False),
        sa.Column("frequency", sa.Integer(), nullable=False),
        sa.Column("is_hidden", sa.Boolean(), nullable=False),
        sa.Column("is_bottleneck", sa.Boolean(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("node_metadata", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_mined_nodes_mining_run_id", "mined_nodes", ["mining_run_id"])
    op.create_table(
        "mined_edges",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("mining_run_id", sa.String(), sa.ForeignKey("mining_runs.id"), nullable=False),
        sa.Column("source_activity", sa.String(), nullable=False),
        sa.Column("target_activity", sa.String(), nullable=False),
        sa.Column("frequency", sa.Integer(), nullable=False),
        sa.Column("avg_wait_hours", sa.Float(), nullable=False),
        sa.Column("is_hidden", sa.Boolean(), nullable=False),
        sa.Column("is_bottleneck", sa.Boolean(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("edge_metadata", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_mined_edges_mining_run_id", "mined_edges", ["mining_run_id"])
    op.create_table(
        "documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("document_metadata", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_documents_source_type", "documents", ["source_type"])
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("document_id", sa.String(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", embedding_type(), nullable=False),
        sa.Column("chunk_metadata", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_source_type", "document_chunks", ["source_type"])
    op.create_table(
        "rag_queries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("mining_run_id", sa.String()),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", json_type(), nullable=False),
        sa.Column("retrieved_chunks", json_type(), nullable=False),
        sa.Column("visible_trace", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "improvement_proposals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("mining_run_id", sa.String(), sa.ForeignKey("mining_runs.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("problem_statement", sa.Text(), nullable=False),
        sa.Column("evidence", json_type(), nullable=False),
        sa.Column("expected_impact", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(), nullable=False),
        sa.Column("required_approvers", json_type(), nullable=False),
        sa.Column("monitoring_kpis", json_type(), nullable=False),
        sa.Column("proposal_metadata", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_improvement_proposals_mining_run_id", "improvement_proposals", ["mining_run_id"])
    op.create_table(
        "improvement_actions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("proposal_id", sa.String(), sa.ForeignKey("improvement_proposals.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("target_system", sa.String(), nullable=False),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("preconditions", json_type(), nullable=False),
        sa.Column("approval_required", sa.Boolean(), nullable=False),
        sa.Column("required_approvers", json_type(), nullable=False),
        sa.Column("expected_config_json", json_type(), nullable=False),
        sa.Column("approval_status", sa.String(), nullable=False),
        sa.Column("approved_by", sa.String()),
        sa.Column("approved_at", sa.DateTime()),
        sa.Column("rejected_by", sa.String()),
        sa.Column("rejected_at", sa.DateTime()),
        sa.Column("approval_comment", sa.Text()),
        sa.Column("action_metadata", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_improvement_actions_proposal_id", "improvement_actions", ["proposal_id"])
    op.create_index("ix_improvement_actions_approval_status", "improvement_actions", ["approval_status"])
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("action_id", sa.String(), sa.ForeignKey("improvement_actions.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("validation_result", json_type(), nullable=False),
        sa.Column("config_json", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_agent_runs_action_id", "agent_runs", ["action_id"])
    op.create_table(
        "agent_steps",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("agent_run_id", sa.String(), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("input_json", json_type(), nullable=False),
        sa.Column("output_json", json_type(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_agent_steps_agent_run_id", "agent_steps", ["agent_run_id"])
    op.create_table(
        "mock_system_configs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("agent_run_id", sa.String(), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("action_id", sa.String(), sa.ForeignKey("improvement_actions.id"), nullable=False),
        sa.Column("target_system", sa.String(), nullable=False),
        sa.Column("configuration_type", sa.String(), nullable=False),
        sa.Column("config_json", json_type(), nullable=False),
        sa.Column("validation_result", json_type(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("requires_final_human_enablement", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_mock_system_configs_agent_run_id", "mock_system_configs", ["agent_run_id"])


def downgrade() -> None:
    for table in [
        "mock_system_configs",
        "agent_steps",
        "agent_runs",
        "improvement_actions",
        "improvement_proposals",
        "rag_queries",
        "document_chunks",
        "documents",
        "mined_edges",
        "mined_nodes",
        "mining_runs",
        "process_events",
        "uploaded_event_logs",
        "ideal_process_edges",
        "ideal_process_nodes",
        "ideal_processes",
    ]:
        op.drop_table(table)

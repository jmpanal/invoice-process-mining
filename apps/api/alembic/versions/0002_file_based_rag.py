from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

try:
    from pgvector.sqlalchemy import Vector
except Exception:
    Vector = None

revision = "0002_file_based_rag"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def embedding_type():
    if Vector is not None:
        return Vector(1536)
    return json_type()


def upgrade() -> None:
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("document_title", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_file_path", sa.String(), nullable=False),
        sa.Column("source_repository", sa.String(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", embedding_type(), nullable=False),
        sa.Column("chunk_metadata", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_document_chunks_source_type", "document_chunks", ["source_type"])
    op.create_index("ix_document_chunks_source_file_path", "document_chunks", ["source_file_path"])


def downgrade() -> None:
    op.drop_table("document_chunks")
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

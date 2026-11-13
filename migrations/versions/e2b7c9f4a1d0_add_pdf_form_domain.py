"""adiciona o domínio de formulários PDF

Revision ID: e2b7c9f4a1d0
Revises: c7a1e9d4b230
Create Date: 2026-11-12 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2b7c9f4a1d0"
down_revision: str | Sequence[str] | None = "c7a1e9d4b230"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria as tabelas de sessões, campos e memória vetorial de PDFs."""
    op.create_table(
        "pdf_fill_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("generation_status", sa.String(length=32), nullable=False),
        sa.Column("generation_progress", sa.Integer(), nullable=False),
        sa.Column("generation_total", sa.Integer(), nullable=False),
        sa.Column("output_path", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_suggested_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("pdf_fill_sessions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_pdf_fill_sessions_source_id"),
            ["source_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_pdf_fill_sessions_status"),
            ["status"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_pdf_fill_sessions_workspace_id"),
            ["workspace_id"],
            unique=False,
        )

    op.create_table(
        "pdf_fill_fields",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("field_type", sa.String(length=32), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("readonly", sa.Boolean(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("current_value", sa.Text(), nullable=True),
        sa.Column("suggested_value", sa.Text(), nullable=True),
        sa.Column("final_value", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("suggestion_source", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("max_length", sa.Integer(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["pdf_fill_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "field_name",
            name="uq_pdf_fill_fields_session_field",
        ),
    )
    with op.batch_alter_table("pdf_fill_fields", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_pdf_fill_fields_session_id"),
            ["session_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_pdf_fill_fields_status"),
            ["status"],
            unique=False,
        )

    op.create_table(
        "pdf_field_memories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("memory_hash", sa.String(length=64), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("field_name", sa.Text(), nullable=False),
        sa.Column("field_type", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("embedding_model", sa.String(length=120), nullable=True),
        sa.Column("embedding_dim", sa.Integer(), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "memory_hash",
            name="uq_pdf_field_memories_workspace_hash",
        ),
    )
    with op.batch_alter_table("pdf_field_memories", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_pdf_field_memories_memory_hash"),
            ["memory_hash"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_pdf_field_memories_source_id"),
            ["source_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_pdf_field_memories_workspace_id"),
            ["workspace_id"],
            unique=False,
        )


def downgrade() -> None:
    """Remove as tabelas de formulários PDF."""
    with op.batch_alter_table("pdf_field_memories", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_pdf_field_memories_workspace_id"))
        batch_op.drop_index(batch_op.f("ix_pdf_field_memories_source_id"))
        batch_op.drop_index(batch_op.f("ix_pdf_field_memories_memory_hash"))

    op.drop_table("pdf_field_memories")

    with op.batch_alter_table("pdf_fill_fields", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_pdf_fill_fields_status"))
        batch_op.drop_index(batch_op.f("ix_pdf_fill_fields_session_id"))

    op.drop_table("pdf_fill_fields")

    with op.batch_alter_table("pdf_fill_sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_pdf_fill_sessions_workspace_id"))
        batch_op.drop_index(batch_op.f("ix_pdf_fill_sessions_status"))
        batch_op.drop_index(batch_op.f("ix_pdf_fill_sessions_source_id"))

    op.drop_table("pdf_fill_sessions")

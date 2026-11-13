"""add source chunks and lexical index

Revision ID: 9e4c1b7a2d10
Revises: 1921eb2cd64a
Create Date: 2026-11-12 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9e4c1b7a2d10"
down_revision: Union[str, Sequence[str], None] = "1921eb2cd64a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create chunks and the FTS5 virtual table."""
    op.create_table(
        "source_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.Text(), nullable=False),
        sa.Column("chunk_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("embedding_model", sa.String(length=120), nullable=True),
        sa.Column("embedding_dim", sa.Integer(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.UniqueConstraint(
            "source_id",
            "chunk_index",
            name="uq_source_chunks_source_chunk",
        ),
    )
    with op.batch_alter_table("source_chunks", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_source_chunks_chunk_hash"),
            ["chunk_hash"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_source_chunks_source_id"),
            ["source_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_source_chunks_workspace_id"),
            ["workspace_id"],
            unique=False,
        )

    op.execute(
        """
        CREATE VIRTUAL TABLE source_chunks_fts USING fts5(
            text,
            section_title,
            page_number UNINDEXED,
            content='source_chunks',
            content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        )
        """
    )
    op.execute(
        """
        CREATE TRIGGER source_chunks_fts_ai
        AFTER INSERT ON source_chunks BEGIN
            INSERT INTO source_chunks_fts(rowid, text, section_title, page_number)
            VALUES (new.id, new.text, new.section_title, new.page_number);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER source_chunks_fts_ad
        AFTER DELETE ON source_chunks BEGIN
            INSERT INTO source_chunks_fts(
                source_chunks_fts,
                rowid,
                text,
                section_title,
                page_number
            )
            VALUES (
                'delete',
                old.id,
                old.text,
                old.section_title,
                old.page_number
            );
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER source_chunks_fts_au
        AFTER UPDATE ON source_chunks BEGIN
            INSERT INTO source_chunks_fts(
                source_chunks_fts,
                rowid,
                text,
                section_title,
                page_number
            )
            VALUES (
                'delete',
                old.id,
                old.text,
                old.section_title,
                old.page_number
            );
            INSERT INTO source_chunks_fts(rowid, text, section_title, page_number)
            VALUES (new.id, new.text, new.section_title, new.page_number);
        END
        """
    )


def downgrade() -> None:
    """Drop chunks and the FTS5 virtual table."""
    op.execute("DROP TRIGGER IF EXISTS source_chunks_fts_au")
    op.execute("DROP TRIGGER IF EXISTS source_chunks_fts_ad")
    op.execute("DROP TRIGGER IF EXISTS source_chunks_fts_ai")
    op.execute("DROP TABLE IF EXISTS source_chunks_fts")

    with op.batch_alter_table("source_chunks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_source_chunks_workspace_id"))
        batch_op.drop_index(batch_op.f("ix_source_chunks_source_id"))
        batch_op.drop_index(batch_op.f("ix_source_chunks_chunk_hash"))

    op.drop_table("source_chunks")

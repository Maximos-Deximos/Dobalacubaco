"""add proposal domain

Revision ID: c7a1e9d4b230
Revises: 9e4c1b7a2d10
Create Date: 2026-11-12 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7a1e9d4b230"
down_revision: Union[str, Sequence[str], None] = "9e4c1b7a2d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create proposals, sections, and revisions."""
    op.create_table(
        "proposals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("proposals", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_proposals_status"),
            ["status"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_proposals_workspace_id"),
            ["workspace_id"],
            unique=False,
        )

    op.create_table(
        "proposal_sections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("proposal_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["proposals.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "proposal_id",
            "key",
            name="uq_proposal_sections_proposal_key",
        ),
    )
    with op.batch_alter_table("proposal_sections", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_proposal_sections_proposal_id"),
            ["proposal_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_proposal_sections_status"),
            ["status"],
            unique=False,
        )

    op.create_table(
        "proposal_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("proposal_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("content_before", sa.Text(), nullable=False),
        sa.Column("content_after", sa.Text(), nullable=False),
        sa.Column("actor", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["proposals.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["section_id"],
            ["proposal_sections.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("proposal_revisions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_proposal_revisions_proposal_id"),
            ["proposal_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_proposal_revisions_section_id"),
            ["section_id"],
            unique=False,
        )


def downgrade() -> None:
    """Drop proposal tables."""
    with op.batch_alter_table("proposal_revisions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_proposal_revisions_section_id"))
        batch_op.drop_index(batch_op.f("ix_proposal_revisions_proposal_id"))

    op.drop_table("proposal_revisions")

    with op.batch_alter_table("proposal_sections", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_proposal_sections_status"))
        batch_op.drop_index(batch_op.f("ix_proposal_sections_proposal_id"))

    op.drop_table("proposal_sections")

    with op.batch_alter_table("proposals", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_proposals_workspace_id"))
        batch_op.drop_index(batch_op.f("ix_proposals_status"))

    op.drop_table("proposals")

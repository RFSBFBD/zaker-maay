"""store extracted document chunks and processing status

Revision ID: 6c419721a122
Revises: c8bd57122514
Create Date: 2026-10-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6c419721a122"
down_revision: Union[str, None] = "c8bd57122514"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("resources") as batch_op:
        batch_op.add_column(
            sa.Column("processing_status", sa.String(length=16), server_default="pending", nullable=False)
        )
        batch_op.create_check_constraint(
            "ck_resource_processing_status",
            "processing_status IN ('pending', 'ready', 'no_text', 'unsupported', 'truncated', 'failed')",
        )
    op.create_table(
        "resource_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("length(trim(content)) > 0", name="ck_resource_chunk_content_nonempty"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resource_id", "chunk_index", name="uq_resource_chunk_index"),
    )
    op.create_index("ix_resource_chunks_resource_id", "resource_chunks", ["resource_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_resource_chunks_resource_id", table_name="resource_chunks")
    op.drop_table("resource_chunks")
    with op.batch_alter_table("resources") as batch_op:
        batch_op.drop_constraint("ck_resource_processing_status", type_="check")
        batch_op.drop_column("processing_status")

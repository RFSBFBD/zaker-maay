"""Add transcript support to YouTube links."""

from typing import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0014_youtube_transcripts"
down_revision: str | None = "0013_study_sessions_per_subject"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    schema = "public" if bind.dialect.name == "postgresql" else None

    # Add columns to youtube_links
    existing = {col["name"] for col in bind.dialect.inspect(bind).get_columns("youtube_links", schema=schema)}
    columns = [
        ("transcript_text", sa.Text()),
        ("transcript_language", sa.String(10)),
        ("processing_status", sa.String(16), "pending"),
    ]
    for col_name, col_type, *default in columns:
        if col_name not in existing:
            kwargs = {"server_default": default[0]} if default else {}
            op.add_column("youtube_links", sa.Column(col_name, col_type, nullable=True, **kwargs), schema=schema)

    # Create youtube_chunks table
    op.create_table(
        "youtube_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("youtube_link_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("youtube_link_id", "chunk_index", name="uq_youtube_chunk_index"),
        sa.ForeignKeyConstraint(["youtube_link_id"], ["youtube_links.id"], ondelete="CASCADE"),
        schema=schema,
    )
    op.create_index("ix_youtube_chunks_link_id", "youtube_chunks", ["youtube_link_id"], schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    schema = "public" if bind.dialect.name == "postgresql" else None
    op.drop_index("ix_youtube_chunks_link_id", table_name="youtube_chunks", schema=schema)
    op.drop_table("youtube_chunks", schema=schema)
    op.drop_column("youtube_links", "processing_status", schema=schema)
    op.drop_column("youtube_links", "transcript_language", schema=schema)
    op.drop_column("youtube_links", "transcript_text", schema=schema)

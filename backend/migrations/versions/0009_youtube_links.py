"""Add subject-scoped YouTube link metadata without fetching video URLs."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0009_youtube_links"
down_revision: str | None = "0008_api_compatibility"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    schema = "public" if op.get_bind().dialect.name == "postgresql" else None
    if inspect(op.get_bind()).has_table("youtube_links", schema=schema):
        return
    op.create_table(
        "youtube_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.String(length=11), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(video_id) = 11", name="ck_youtube_link_video_id_length"),
        sa.ForeignKeyConstraint(["owner_id"], ["profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject_id", "video_id", name="uq_youtube_link_subject_video"),
        schema=schema,
    )
    op.create_index("ix_youtube_links_subject_created", "youtube_links", ["subject_id", "created_at"], schema=schema)


def downgrade() -> None:
    # Preserve video link metadata during rollbacks; deletion needs an explicit data policy.
    pass

"""Add video learning, visual analysis, and timestamp columns.

Revision ID: 0020_video_learning
Revises: 0019_batch_uploads
"""

from typing import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0020_video_learning"
down_revision: str | None = "0019_batch_uploads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    schema = "public" if bind.dialect.name == "postgresql" else None
    inspector = inspect(bind)

    # 1. Update youtube_links table
    yt_cols = {col["name"] for col in inspector.get_columns("youtube_links", schema=schema)}

    new_yt_cols = [
        ("channel_name", sa.String(255), True, None),
        ("duration_seconds", sa.Integer(), True, None),
        ("published_at", sa.DateTime(timezone=True), True, None),
        ("description", sa.Text(), True, None),
        ("markdown_storage_key", sa.String(512), True, None),
        ("markdown_storage_bucket", sa.String(128), True, None),
        ("visual_analysis_status", sa.String(32), False, "pending"),
        ("visual_summary", sa.Text(), True, None),
        ("academic_chapter", sa.Integer(), True, None),
        ("chapter_title", sa.String(255), True, None),
        ("video_metadata", sa.JSON(), False, sa.text("'{}'")),
    ]

    for name, col_type, is_nullable, server_def in new_yt_cols:
        if name not in yt_cols:
            kwargs = {"nullable": is_nullable}
            if server_def is not None:
                kwargs["server_default"] = server_def
            op.add_column("youtube_links", sa.Column(name, col_type, **kwargs))

    # 2. Update youtube_chunks table
    chunk_cols = {col["name"] for col in inspector.get_columns("youtube_chunks", schema=schema)}

    new_chunk_cols = [
        ("start_seconds", sa.Float(), True, None),
        ("end_seconds", sa.Float(), True, None),
        ("segment_title", sa.String(255), True, None),
        ("visual_description", sa.Text(), True, None),
        ("created_at", sa.DateTime(timezone=True), False, sa.func.now()),
    ]

    for name, col_type, is_nullable, server_def in new_chunk_cols:
        if name not in chunk_cols:
            kwargs = {"nullable": is_nullable}
            if server_def is not None:
                kwargs["server_default"] = server_def
            op.add_column("youtube_chunks", sa.Column(name, col_type, **kwargs))


def downgrade() -> None:
    bind = op.get_bind()
    schema = "public" if bind.dialect.name == "postgresql" else None
    inspector = inspect(bind)

    chunk_cols = {col["name"] for col in inspector.get_columns("youtube_chunks", schema=schema)}
    for col in ["created_at", "visual_description", "segment_title", "end_seconds", "start_seconds"]:
        if col in chunk_cols:
            op.drop_column("youtube_chunks", col)

    yt_cols = {col["name"] for col in inspector.get_columns("youtube_links", schema=schema)}
    for col in [
        "video_metadata",
        "chapter_title",
        "academic_chapter",
        "visual_summary",
        "visual_analysis_status",
        "markdown_storage_bucket",
        "markdown_storage_key",
        "description",
        "published_at",
        "duration_seconds",
        "channel_name",
    ]:
        if col in yt_cols:
            op.drop_column("youtube_links", col)

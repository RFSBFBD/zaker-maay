"""Add opt-in audio transcript fields to resources."""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0010_audio_transcripts"
down_revision: str | None = "0009_youtube_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    schema = "public" if op.get_bind().dialect.name == "postgresql" else None
    existing = {column["name"] for column in inspect(op.get_bind()).get_columns("resources", schema=schema)}
    columns = (
        sa.Column("transcript_text", sa.Text(), nullable=True),
        sa.Column("transcript_language", sa.String(length=35), nullable=True),
        sa.Column("transcription_model", sa.String(length=100), nullable=True),
        sa.Column("audio_duration_seconds", sa.Integer(), nullable=True),
    )
    for column in columns:
        if column.name not in existing:
            op.add_column("resources", column, schema=schema)


def downgrade() -> None:
    # Preserve transcripts through rollback; removing user content needs a separate decision.
    pass

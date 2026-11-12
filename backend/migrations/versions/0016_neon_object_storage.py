"""Add storage_provider, storage_bucket, storage_key to resources for Neon Object Storage.

Revision ID: 0016_neon_object_storage
Revises: 0015_orchestrator
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision: str = "0016_neon_object_storage"
down_revision: str | None = "0015_orchestrator"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    schema = "public" if bind.dialect.name == "postgresql" else None
    existing_cols = {col["name"] for col in inspect(bind).get_columns("resources", schema=schema)}

    if "storage_provider" not in existing_cols:
        op.add_column(
            "resources",
            sa.Column("storage_provider", sa.String(32), server_default="neon", nullable=False),
            schema=schema,
        )

    if "storage_bucket" not in existing_cols:
        op.add_column(
            "resources",
            sa.Column("storage_bucket", sa.String(128), nullable=True),
            schema=schema,
        )

    if "storage_key" not in existing_cols:
        op.add_column(
            "resources",
            sa.Column("storage_key", sa.String(512), nullable=True),
            schema=schema,
        )

    # Make cloudinary_public_id nullable if supported
    if bind.dialect.name == "postgresql":
        op.alter_column("resources", "cloudinary_public_id", nullable=True, schema=schema)

    # For existing legacy rows created before this migration, mark storage_provider as cloudinary
    bind.execute(
        text(
            "UPDATE resources SET storage_provider = 'cloudinary' "
            "WHERE storage_key IS NULL AND cloudinary_public_id IS NOT NULL "
            "AND cloudinary_public_id NOT LIKE 'gemini-resource/%' "
            "AND cloudinary_public_id NOT LIKE 'audio-transcript/%' "
            "AND cloudinary_public_id NOT LIKE 'direct-resource/%'"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    schema = "public" if bind.dialect.name == "postgresql" else None
    existing_cols = {col["name"] for col in inspect(bind).get_columns("resources", schema=schema)}

    if "storage_key" in existing_cols:
        op.drop_column("resources", "storage_key", schema=schema)
    if "storage_bucket" in existing_cols:
        op.drop_column("resources", "storage_bucket", schema=schema)
    if "storage_provider" in existing_cols:
        op.drop_column("resources", "storage_provider", schema=schema)

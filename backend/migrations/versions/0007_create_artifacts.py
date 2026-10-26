"""Baseline marker for the existing Neon schema.

Revision ID: 0007_create_artifacts
Revises:

The Neon database already contains the schema recorded by this revision. The
marker is intentionally a no-op; the separate `neon_existing_schema` branch
adds only API compatibility objects and leaves this baseline untouched.
"""

from typing import Sequence

revision: str = "0007_create_artifacts"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("neon_existing_schema",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    # Never remove an existing database schema from its baseline marker.
    pass

"""Scope study sessions per subject."""

from typing import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision: str = "0013_study_sessions_per_subject"
down_revision: str | None = "0012_admin_ai_configs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Drop old global active user index/constraint
    if dialect == "postgresql":
        try:
            op.drop_index("uq_study_sessions_active_user", table_name="study_sessions")
        except Exception:
            pass
        # Create new per-subject active user index
        op.create_index(
            "uq_study_sessions_active_user_subject",
            "study_sessions",
            ["user_id", "subject_id"],
            unique=True,
            postgresql_where=text("status = 'active'"),
        )
    else:
        try:
            op.drop_index("uq_study_sessions_active_user", table_name="study_sessions")
        except Exception:
            pass
        op.create_index(
            "uq_study_sessions_active_user_subject",
            "study_sessions",
            ["user_id", "subject_id"],
            unique=True,
            sqlite_where=text("status = 'active'"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    try:
        op.drop_index("uq_study_sessions_active_user_subject", table_name="study_sessions")
    except Exception:
        pass
    if dialect == "postgresql":
        op.create_index(
            "uq_study_sessions_active_user",
            "study_sessions",
            ["user_id"],
            unique=True,
            postgresql_where=text("status = 'active'"),
        )
    else:
        op.create_index(
            "uq_study_sessions_active_user",
            "study_sessions",
            ["user_id"],
            unique=True,
            sqlite_where=text("status = 'active'"),
        )


"""Extend proctoring sessions for secure recording and violation tracking.

Revision ID: e8b41c6d903f
Revises: f3a91c7d2e60
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8b41c6d903f"
down_revision: Union[str, Sequence[str], None] = "f3a91c7d2e60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Secure recording metadata
    op.add_column(
        "proctoring_sessions",
        sa.Column("recording_filename", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "proctoring_sessions",
        sa.Column("recording_path", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "proctoring_sessions",
        sa.Column("recording_mime_type", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "proctoring_sessions",
        sa.Column("recording_size_bytes", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "proctoring_sessions",
        sa.Column("recording_started_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "proctoring_sessions",
        sa.Column("recording_completed_at", sa.DateTime(), nullable=True),
    )

    # Automatic deletion tracking
    op.add_column(
        "proctoring_sessions",
        sa.Column("delete_after", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "proctoring_sessions",
        sa.Column("recording_deleted_at", sa.DateTime(), nullable=True),
    )

    # Proctoring violation tracking
    op.add_column(
        "proctoring_sessions",
        sa.Column(
            "warning_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "proctoring_sessions",
        sa.Column(
            "is_flagged_for_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "proctoring_sessions",
        sa.Column("last_violation_type", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "proctoring_sessions",
        sa.Column("last_violation_at", sa.DateTime(), nullable=True),
    )

    op.create_index(
        "ix_proctoring_sessions_delete_after",
        "proctoring_sessions",
        ["delete_after"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_proctoring_sessions_delete_after",
        table_name="proctoring_sessions",
    )

    op.drop_column("proctoring_sessions", "last_violation_at")
    op.drop_column("proctoring_sessions", "last_violation_type")
    op.drop_column("proctoring_sessions", "is_flagged_for_review")
    op.drop_column("proctoring_sessions", "warning_count")
    op.drop_column("proctoring_sessions", "recording_deleted_at")
    op.drop_column("proctoring_sessions", "delete_after")
    op.drop_column("proctoring_sessions", "recording_completed_at")
    op.drop_column("proctoring_sessions", "recording_started_at")
    op.drop_column("proctoring_sessions", "recording_size_bytes")
    op.drop_column("proctoring_sessions", "recording_mime_type")
    op.drop_column("proctoring_sessions", "recording_path")
    op.drop_column("proctoring_sessions", "recording_filename")


"""add_proctoring_sessions

Revision ID: d92e6f4a1b30
Revises: c4acb5370e21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d92e6f4a1b30"
down_revision: Union[str, Sequence[str], None] = "c4acb5370e21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proctoring_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("consent_given", sa.Boolean(), nullable=False),
        sa.Column("consent_version", sa.String(length=50), nullable=True),
        sa.Column("consented_at", sa.DateTime(), nullable=True),
        sa.Column("camera_permission_granted", sa.Boolean(), nullable=False),
        sa.Column("session_status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["assessment_assignments.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assignment_id",
            name="uq_proctoring_session_assignment",
        ),
    )

    op.create_index(
        "ix_proctoring_sessions_assignment_id",
        "proctoring_sessions",
        ["assignment_id"],
    )
    op.create_index(
        "ix_proctoring_sessions_candidate_id",
        "proctoring_sessions",
        ["candidate_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_proctoring_sessions_candidate_id",
        table_name="proctoring_sessions",
    )
    op.drop_index(
        "ix_proctoring_sessions_assignment_id",
        table_name="proctoring_sessions",
    )
    op.drop_table("proctoring_sessions")

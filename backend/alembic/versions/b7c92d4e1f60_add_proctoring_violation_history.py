
"""Add proctoring violation history

Revision ID: b7c92d4e1f60
Revises: e8b41c6d903f
"""

from alembic import op
import sqlalchemy as sa


revision = "b7c92d4e1f60"
down_revision = "e8b41c6d903f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "proctoring_violations",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True
        ),

        sa.Column(
            "proctoring_session_id",
            sa.Integer(),
            sa.ForeignKey(
                "proctoring_sessions.id",
                ondelete="CASCADE"
            ),
            nullable=False
        ),

        sa.Column(
            "assignment_id",
            sa.Integer(),
            sa.ForeignKey(
                "assessment_assignments.id",
                ondelete="CASCADE"
            ),
            nullable=False
        ),

        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey(
                "candidates.id",
                ondelete="CASCADE"
            ),
            nullable=False
        ),

        sa.Column(
            "violation_type",
            sa.String(length=100),
            nullable=False
        ),

        sa.Column(
            "confidence",
            sa.Float(),
            nullable=True
        ),

        sa.Column(
            "details",
            sa.JSON(),
            nullable=True
        ),

        sa.Column(
            "detected_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now()
        ),
    )

    op.create_index(
        "ix_proctoring_violations_session",
        "proctoring_violations",
        ["proctoring_session_id"]
    )

    op.create_index(
        "ix_proctoring_violations_assignment",
        "proctoring_violations",
        ["assignment_id"]
    )

    op.create_index(
        "ix_proctoring_violations_candidate",
        "proctoring_violations",
        ["candidate_id"]
    )

    op.create_index(
        "ix_proctoring_violations_type",
        "proctoring_violations",
        ["violation_type"]
    )

    op.create_index(
        "ix_proctoring_violations_detected_at",
        "proctoring_violations",
        ["detected_at"]
    )


def downgrade():
    op.drop_table("proctoring_violations")

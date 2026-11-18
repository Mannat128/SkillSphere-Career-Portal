"""Add manual recruiter assessment review workflow.

Revision ID: b7ab99c251c8
Revises: 9c4e2a7b6d10
"""

from alembic import op
import sqlalchemy as sa


revision = "b7ab99c251c8"
down_revision = "9c4e2a7b6d10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_assessment_results",
        sa.Column(
            "review_status",
            sa.String(length=30),
            nullable=False,
            server_default="PENDING_REVIEW",
        ),
    )

    op.add_column(
        "candidate_assessment_results",
        sa.Column(
            "reviewed_by_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "candidate_assessment_results",
        sa.Column(
            "reviewed_at",
            sa.DateTime(),
            nullable=True,
        ),
    )

    op.add_column(
        "candidate_assessment_results",
        sa.Column(
            "review_notes",
            sa.Text(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_candidate_assessment_results_review_status",
        "candidate_assessment_results",
        ["review_status"],
        unique=False,
    )

    op.create_index(
        "ix_candidate_assessment_results_reviewed_by_id",
        "candidate_assessment_results",
        ["reviewed_by_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_candidate_assessment_results_reviewed_by_id_users",
        "candidate_assessment_results",
        "users",
        ["reviewed_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_candidate_assessment_results_reviewed_by_id_users",
        "candidate_assessment_results",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_candidate_assessment_results_reviewed_by_id",
        table_name="candidate_assessment_results",
    )

    op.drop_index(
        "ix_candidate_assessment_results_review_status",
        table_name="candidate_assessment_results",
    )

    op.drop_column(
        "candidate_assessment_results",
        "review_notes",
    )

    op.drop_column(
        "candidate_assessment_results",
        "reviewed_at",
    )

    op.drop_column(
        "candidate_assessment_results",
        "reviewed_by_id",
    )

    op.drop_column(
        "candidate_assessment_results",
        "review_status",
    )
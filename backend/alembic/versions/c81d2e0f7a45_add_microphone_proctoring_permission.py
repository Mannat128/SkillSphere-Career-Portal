"""Track microphone permission for assessment proctoring."""

from alembic import op
import sqlalchemy as sa


revision = "c81d2e0f7a45"
down_revision = "8f42c6b0a311"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proctoring_sessions",
        sa.Column("microphone_permission_granted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("proctoring_sessions", "microphone_permission_granted", server_default=None)
    op.add_column("job_assessments", sa.Column("available_from", sa.DateTime(), nullable=True))
    op.add_column("job_assessments", sa.Column("available_until", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("proctoring_sessions", "microphone_permission_granted")
    op.drop_column("job_assessments", "available_until")
    op.drop_column("job_assessments", "available_from")

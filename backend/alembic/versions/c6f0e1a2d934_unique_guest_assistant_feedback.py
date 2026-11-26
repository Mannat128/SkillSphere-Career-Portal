"""Enforce one assistant feedback row per guest session and answer."""

from alembic import op


revision = "c6f0e1a2d934"
down_revision = "a62c9e14f731"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_assistant_feedback_guest_message",
        "assistant_feedback",
        ["message_id", "guest_session_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_assistant_feedback_guest_message",
        table_name="assistant_feedback",
    )

"""Add session-owned local assistant, feedback, and unanswered-question workflows."""

from alembic import op
import sqlalchemy as sa


revision = "a62c9e14f731"
down_revision = "d9f2a4b7c601"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sphera_conversations") as batch:
        batch.alter_column("user_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("guest_session_hash", sa.String(64), nullable=True))
        batch.add_column(sa.Column("selected_language", sa.String(16), nullable=False, server_default="auto"))
        batch.add_column(sa.Column("last_intent", sa.String(80), nullable=True))
        batch.add_column(sa.Column("last_confidence", sa.Float(), nullable=True))
        batch.create_index("ix_sphera_conversations_guest_session_hash", ["guest_session_hash"])

    with op.batch_alter_table("sphera_messages") as batch:
        batch.add_column(sa.Column("intent", sa.String(80), nullable=True))
        batch.add_column(sa.Column("confidence", sa.Float(), nullable=True))
        batch.add_column(sa.Column("language", sa.String(16), nullable=True))

    op.create_table(
        "assistant_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("guest_session_hash", sa.String(64), nullable=True),
        sa.Column("user_role", sa.String(32), nullable=False),
        sa.Column("rating", sa.String(16), nullable=False),
        sa.Column("category", sa.String(40), nullable=True),
        sa.Column("comment", sa.String(1000), nullable=True),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("matched_intent", sa.String(80), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("admin_notes", sa.String(2000), nullable=True),
        sa.Column("assigned_admin_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["sphera_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["sphera_conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_admin_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", "user_id", name="uq_assistant_feedback_user_message"),
    )
    for column in ("message_id", "conversation_id", "user_id", "guest_session_hash", "status", "priority", "created_at"):
        op.create_index(f"ix_assistant_feedback_{column}", "assistant_feedback", [column])
    op.create_index("ix_assistant_feedback_status_priority", "assistant_feedback", ["status", "priority"])

    op.create_table(
        "assistant_unanswered_questions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("query_hash", sa.String(64), nullable=False),
        sa.Column("normalized_query", sa.String(500), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("best_intent", sa.String(80), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("frequency", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("query_hash", "language", name="uq_assistant_unanswered_query_language"),
    )
    for column in ("query_hash", "language", "review_status"):
        op.create_index(f"ix_assistant_unanswered_questions_{column}", "assistant_unanswered_questions", [column])

    op.create_table(
        "assistant_knowledge_suggestions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("unanswered_id", sa.Integer(), nullable=True),
        sa.Column("intent_id", sa.String(80), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("question", sa.String(500), nullable=False),
        sa.Column("response", sa.String(2000), nullable=False),
        sa.Column("route", sa.String(160), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["unanswered_id"], ["assistant_unanswered_questions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("unanswered_id", "status"):
        op.create_index(f"ix_assistant_knowledge_suggestions_{column}", "assistant_knowledge_suggestions", [column])


def downgrade() -> None:
    op.drop_table("assistant_knowledge_suggestions")
    op.drop_table("assistant_unanswered_questions")
    op.drop_table("assistant_feedback")
    with op.batch_alter_table("sphera_messages") as batch:
        batch.drop_column("language")
        batch.drop_column("confidence")
        batch.drop_column("intent")
    with op.batch_alter_table("sphera_conversations") as batch:
        batch.drop_index("ix_sphera_conversations_guest_session_hash")
        batch.drop_column("last_confidence")
        batch.drop_column("last_intent")
        batch.drop_column("selected_language")
        batch.drop_column("guest_session_hash")
        batch.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

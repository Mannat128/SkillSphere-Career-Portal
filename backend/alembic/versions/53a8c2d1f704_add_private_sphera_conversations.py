"""Add private, authenticated Sphera conversation history."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "53a8c2d1f704"
down_revision: Union[str, Sequence[str], None] = "e8b41c6d903f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sphera_conversations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sphera_conversations_id", "sphera_conversations", ["id"], unique=False
    )
    op.create_index(
        "ix_sphera_conversations_user_id", "sphera_conversations", ["user_id"], unique=False
    )
    op.create_index(
        "ix_sphera_conversations_user_updated",
        "sphera_conversations",
        ["user_id", "updated_at"],
        unique=False,
    )
    op.create_table(
        "sphera_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["sphera_conversations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sphera_messages_id", "sphera_messages", ["id"], unique=False)
    op.create_index(
        "ix_sphera_messages_conversation_id",
        "sphera_messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_sphera_messages_conversation_created",
        "sphera_messages",
        ["conversation_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sphera_messages_conversation_created", table_name="sphera_messages")
    op.drop_index("ix_sphera_messages_conversation_id", table_name="sphera_messages")
    op.drop_index("ix_sphera_messages_id", table_name="sphera_messages")
    op.drop_table("sphera_messages")
    op.drop_index("ix_sphera_conversations_user_updated", table_name="sphera_conversations")
    op.drop_index("ix_sphera_conversations_user_id", table_name="sphera_conversations")
    op.drop_index("ix_sphera_conversations_id", table_name="sphera_conversations")
    op.drop_table("sphera_conversations")

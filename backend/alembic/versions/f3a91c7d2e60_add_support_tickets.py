
"""add_support_tickets

Revision ID: f3a91c7d2e60
Revises: d92e6f4a1b30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a91c7d2e60"
down_revision: Union[str, Sequence[str], None] = "d92e6f4a1b30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_table(
        "support_tickets",

        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_number", sa.String(length=30), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("assigned_admin_id", sa.Integer(), nullable=True),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),

        sa.Column(
            "category",
            sa.Enum(
                "ACCOUNT",
                "JOB_APPLICATION",
                "ASSESSMENT",
                "TECHNICAL",
                "PAYMENT",
                "OTHER",
                name="ticketcategory",
            ),
            nullable=False,
        ),

        sa.Column(
            "priority",
            sa.Enum(
                "LOW",
                "MEDIUM",
                "HIGH",
                "URGENT",
                name="ticketpriority",
            ),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "IN_PROGRESS",
                "RESOLVED",
                "CLOSED",
                name="ticketstatus",
            ),
            nullable=False,
        ),

        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),

        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["assigned_admin_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),

        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_number"),
    )

    op.create_index(
        "ix_support_tickets_id",
        "support_tickets",
        ["id"],
    )

    op.create_index(
        "ix_support_tickets_ticket_number",
        "support_tickets",
        ["ticket_number"],
    )

    op.create_index(
        "ix_support_tickets_created_by_id",
        "support_tickets",
        ["created_by_id"],
    )

    op.create_index(
        "ix_support_tickets_status",
        "support_tickets",
        ["status"],
    )

    op.create_table(
        "ticket_messages",

        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_admin_reply", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),

        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["support_tickets.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["sender_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_ticket_messages_id",
        "ticket_messages",
        ["id"],
    )

    op.create_index(
        "ix_ticket_messages_ticket_id",
        "ticket_messages",
        ["ticket_id"],
    )

    op.create_table(
        "ticket_attachments",

        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),

        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["support_tickets.id"],
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["uploaded_by_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_filename"),
    )

    op.create_index(
        "ix_ticket_attachments_id",
        "ticket_attachments",
        ["id"],
    )

    op.create_index(
        "ix_ticket_attachments_ticket_id",
        "ticket_attachments",
        ["ticket_id"],
    )


def downgrade() -> None:

    op.drop_index(
        "ix_ticket_attachments_ticket_id",
        table_name="ticket_attachments",
    )

    op.drop_index(
        "ix_ticket_attachments_id",
        table_name="ticket_attachments",
    )

    op.drop_table("ticket_attachments")

    op.drop_index(
        "ix_ticket_messages_ticket_id",
        table_name="ticket_messages",
    )

    op.drop_index(
        "ix_ticket_messages_id",
        table_name="ticket_messages",
    )

    op.drop_table("ticket_messages")

    op.drop_index(
        "ix_support_tickets_status",
        table_name="support_tickets",
    )

    op.drop_index(
        "ix_support_tickets_created_by_id",
        table_name="support_tickets",
    )

    op.drop_index(
        "ix_support_tickets_ticket_number",
        table_name="support_tickets",
    )

    op.drop_index(
        "ix_support_tickets_id",
        table_name="support_tickets",
    )

    op.drop_table("support_tickets")

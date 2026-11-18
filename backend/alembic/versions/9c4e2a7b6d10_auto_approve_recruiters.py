"""Automatically approve existing recruiter accounts.

Revision ID: 9c4e2a7b6d10
Revises: b7c92d4e1f60
Create Date: 2026-11-18
"""

from typing import Sequence, Union

from alembic import op


# Revision identifiers
revision: str = "9c4e2a7b6d10"

down_revision: Union[str, Sequence[str], None] = "b7c92d4e1f60"

branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Automatically approve existing recruiters who are pending.

    Recruiter registration no longer requires Admin approval.
    Admin approval is required only for job postings.
    """

    op.execute(
        """
        UPDATE recruiters
        SET approval_status = 'APPROVED',
            approved_at = COALESCE(approved_at, CURRENT_TIMESTAMP)
        WHERE approval_status = 'PENDING'
        """
    )


def downgrade() -> None:
    """
    Intentionally does not revert recruiter approval statuses.

    Reverting these statuses to PENDING would restore the removed
    recruiter-registration approval restriction.
    """
    pass
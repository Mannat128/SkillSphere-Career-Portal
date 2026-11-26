"""Add candidate professional links and project metadata."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "71c3a4e92fd0"
down_revision: Union[str, Sequence[str], None] = "53a8c2d1f704"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for column in ("contact_email", "linkedin_url", "github_url", "portfolio_url", "additional_url"):
        op.add_column("candidates", sa.Column(column, sa.String(length=500), nullable=True))
    for column in ("github_url", "image_url"):
        op.add_column("candidate_projects", sa.Column(column, sa.String(length=500), nullable=True))
    for column in ("start_date", "end_date"):
        op.add_column("candidate_projects", sa.Column(column, sa.String(length=20), nullable=True))


def downgrade() -> None:
    for column in ("end_date", "start_date", "image_url", "github_url"):
        op.drop_column("candidate_projects", column)
    for column in ("additional_url", "portfolio_url", "github_url", "linkedin_url", "contact_email"):
        op.drop_column("candidates", column)

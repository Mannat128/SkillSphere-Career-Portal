"""Store Cloudinary identifiers for authenticated recordings."""

from alembic import op
import sqlalchemy as sa


revision = "d9f2a4b7c601"
down_revision = "c81d2e0f7a45"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proctoring_sessions", sa.Column("recording_provider", sa.String(length=30), nullable=True))
    op.add_column("proctoring_sessions", sa.Column("cloudinary_asset_id", sa.String(length=128), nullable=True))
    op.add_column("proctoring_sessions", sa.Column("cloudinary_public_id", sa.String(length=255), nullable=True))
    op.add_column("proctoring_sessions", sa.Column("cloudinary_version", sa.String(length=50), nullable=True))
    op.add_column("proctoring_sessions", sa.Column("cloudinary_format", sa.String(length=20), nullable=True))
    op.add_column("proctoring_sessions", sa.Column("cloudinary_resource_type", sa.String(length=20), nullable=True))
    op.add_column("proctoring_sessions", sa.Column("cloudinary_delivery_type", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("proctoring_sessions", "cloudinary_delivery_type")
    op.drop_column("proctoring_sessions", "cloudinary_resource_type")
    op.drop_column("proctoring_sessions", "cloudinary_format")
    op.drop_column("proctoring_sessions", "cloudinary_version")
    op.drop_column("proctoring_sessions", "cloudinary_public_id")
    op.drop_column("proctoring_sessions", "cloudinary_asset_id")
    op.drop_column("proctoring_sessions", "recording_provider")

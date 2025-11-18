"""
add first_page_side to users

Revision ID: 0005_add_first_page_side
Revises: 0004_add_user_profile_fields
Create Date: 2025-01-15 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0005_add_first_page_side'
down_revision = '0004_add_user_profile_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем колонку first_page_side с дефолтным значением 'right'
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS first_page_side VARCHAR(10) DEFAULT 'right'"
    )


def downgrade() -> None:
    op.drop_column('users', 'first_page_side')


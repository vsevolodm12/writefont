"""
add username and profile fields to users

Revision ID: 0004_add_user_profile_fields
Revises: 0003_add_fonts_table
Create Date: 2025-11-12 15:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004_add_user_profile_fields'
down_revision = '0003_add_fonts_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('username', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('first_name', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('last_name', sa.Text(), nullable=True))
    op.add_column(
        'users',
        sa.Column(
            'last_seen_at',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
    )

    # заполнить колонку last_seen_at историческими значениями
    op.execute(
        "UPDATE users SET last_seen_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)"
    )


def downgrade() -> None:
    op.drop_column('users', 'last_seen_at')
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'first_name')
    op.drop_column('users', 'username')



"""add fonts table

Revision ID: 0003_add_fonts_table
Revises: 0002_add_grid_and_recent_fonts
Create Date: 2025-11-09 14:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003_add_fonts_table'
down_revision = '0002_add_grid_and_recent_fonts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'fonts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('path', sa.Text(), nullable=False),
        sa.Column('font_type', sa.String(length=32), nullable=False),
        sa.Column('supports_cyrillic_lower', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
        sa.Column('supports_cyrillic_upper', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
        sa.Column('supports_latin_lower', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
        sa.Column('supports_latin_upper', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
        sa.Column('supports_digits', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
        sa.Column('supports_symbols', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
        sa.Column('coverage_score', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('is_base', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.UniqueConstraint('user_id', 'path', name='uq_fonts_user_path'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE')
    )

    op.create_index('idx_fonts_user_type', 'fonts', ['user_id', 'font_type'])
    op.create_index('idx_fonts_user_is_base', 'fonts', ['user_id', 'is_base'])


def downgrade() -> None:
    op.drop_index('idx_fonts_user_is_base', table_name='fonts')
    op.drop_index('idx_fonts_user_type', table_name='fonts')
    op.drop_table('fonts')


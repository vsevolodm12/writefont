from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_add_grid_and_recent_fonts'
down_revision = '0001_create_users_and_jobs'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # grid_enabled
    op.execute(sa.text("ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS grid_enabled BOOLEAN DEFAULT FALSE"))

    # user_recent_fonts
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS user_recent_fonts (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                font_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_user_recent_fonts_user_time
            ON user_recent_fonts (user_id, created_at DESC);
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS idx_user_recent_fonts_user_time"))
    op.execute(sa.text("DROP TABLE IF EXISTS user_recent_fonts"))
    # Не удаляем колонку grid_enabled при даунгрейде (чтобы не терять данные)







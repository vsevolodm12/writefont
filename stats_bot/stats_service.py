from dataclasses import dataclass
from typing import List

from psycopg2.extras import RealDictRow

from stats_bot.config import Settings
from stats_bot.database import get_cursor


@dataclass
class RecentUser:
    user_id: int
    username: str
    pdf_count: int


@dataclass
class Stats:
    new_users_today: int
    total_users: int
    pdf_today: int
    pdf_total: int
    recent_users: List[RecentUser]


def _safe_username(row: RealDictRow) -> str:
    # в основной БД username может отсутствовать
    username = row.get("username")
    if username:
        return username
    return "—"


def fetch_stats(settings: Settings) -> Stats:
    with get_cursor(settings) as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM users
            WHERE created_at >= current_date
            """
        )
        new_users_today = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) AS cnt FROM users")
        total_users = cursor.fetchone()["cnt"]

        cursor.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM jobs
            WHERE status = 'completed'
              AND created_at >= current_date
            """
        )
        pdf_today = cursor.fetchone()["cnt"]

        cursor.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM jobs
            WHERE status = 'completed'
            """
        )
        pdf_total = cursor.fetchone()["cnt"]

        cursor.execute(
            """
            SELECT
                u.user_id,
                NULL::text AS username,
                COUNT(j.*) AS pdf_count,
                MAX(j.completed_at) AS last_completed_at
            FROM users u
            JOIN jobs j ON j.user_id = u.user_id AND j.status = 'completed'
            GROUP BY u.user_id
            ORDER BY last_completed_at DESC NULLS LAST
            LIMIT 5
            """
        )
        rows = cursor.fetchall()

    recent_users = [
        RecentUser(
            user_id=row["user_id"],
            username=_safe_username(row),
            pdf_count=row["pdf_count"],
        )
        for row in rows
    ]

    return Stats(
        new_users_today=new_users_today,
        total_users=total_users,
        pdf_today=pdf_today,
        pdf_total=pdf_total,
        recent_users=recent_users,
    )


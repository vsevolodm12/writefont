import os
from dataclasses import dataclass
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()


def _parse_admin_ids(raw: Optional[str]) -> List[int]:
    if not raw:
        return []
    ids: List[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            ids.append(int(chunk))
        except ValueError:
            continue
    return ids


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: List[int]
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    report_channel_id: Optional[int]


def get_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is required")

    raw_port = os.getenv("DB_PORT", "5432")
    try:
        db_port = int(raw_port)
    except ValueError:
        raise RuntimeError(f"Invalid DB_PORT value: {raw_port}")

    raw_channel = os.getenv("REPORT_CHANNEL_ID", "").strip()
    channel_id = int(raw_channel) if raw_channel else None

    return Settings(
        bot_token=token,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS")),  # не используется, но оставляем для совместимости
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=db_port,
        db_name=os.getenv("DB_NAME", "consp_bot"),
        db_user=os.getenv("DB_USER", "postgres"),
        db_password=os.getenv("DB_PASSWORD", ""),
        report_channel_id=channel_id,
    )


from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.extras import RealDictCursor

from config import Settings


@contextmanager
def get_connection(settings: Settings) -> Iterator[psycopg2.extensions.connection]:
    conn = psycopg2.connect(
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
    )
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_cursor(settings: Settings) -> Iterator[psycopg2.extensions.cursor]:
    with get_connection(settings) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            yield cursor


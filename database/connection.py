"""
Модуль для работы с подключением к базе данных PostgreSQL.
Поддерживает пул соединений для лучшей производительности.
"""

import psycopg2
from psycopg2 import pool
import os
from dotenv import load_dotenv

load_dotenv()

# Глобальный пул соединений
_connection_pool = None


def init_connection_pool():
    """Инициализирует пул соединений"""
    global _connection_pool
    if _connection_pool is None:
        try:
            _connection_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,      # Минимум соединений
                maxconn=20,     # Максимум соединений
                dbname=os.getenv('DB_NAME', 'consp_bot'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', ''),
                host=os.getenv('DB_HOST', 'localhost'),
                port=os.getenv('DB_PORT', '5432'),
                connect_timeout=5
            )
        except psycopg2.OperationalError as e:
            raise ConnectionError(f"Не удалось создать пул соединений: {e}")
        except Exception as e:
            raise ConnectionError(f"Ошибка создания пула: {e}")
    return _connection_pool


def get_db_connection():
    """Возвращает подключение из пула"""
    global _connection_pool
    if _connection_pool is None:
        init_connection_pool()
    
    try:
        return _connection_pool.getconn()
    except psycopg2.pool.PoolError:
        raise ConnectionError("Не удалось получить соединение из пула (все соединения заняты)")
    except Exception as e:
        raise ConnectionError(f"Ошибка получения соединения: {e}")


def return_db_connection(conn):
    """Возвращает соединение в пул (используйте вместо conn.close())"""
    global _connection_pool
    if _connection_pool and conn:
        try:
            _connection_pool.putconn(conn)
        except Exception as e:
            # Если соединение повреждено, закрываем его
            try:
                conn.close()
            except:
                pass


# Инициализируем пул при импорте
try:
    init_connection_pool()
except Exception as e:
    # Если не удалось инициализировать, будет ошибка при первом использовании
    pass


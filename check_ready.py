"""
Скрипт проверки готовности бота к запуску
"""

import os
import sys
from pathlib import Path

def check_env_file():
    """Проверяет наличие и заполненность .env файла"""
    print("1. Проверка .env файла...")
    if not os.path.exists('.env'):
        print("   ✗ Файл .env не найден")
        print("   → Создайте: cp .env.example .env")
        return False
    
    from dotenv import load_dotenv
    load_dotenv()
    
    issues = []
    if not os.getenv('BOT_TOKEN'):
        issues.append("BOT_TOKEN не установлен")
    if not os.getenv('ADMIN_USER_ID'):
        issues.append("ADMIN_USER_ID не установлен")
    if not os.getenv('DB_PASSWORD'):
        issues.append("DB_PASSWORD не установлен")
    
    if issues:
        print(f"   ✗ Проблемы:")
        for issue in issues:
            print(f"     - {issue}")
        return False
    
    print("   ✓ .env файл настроен")
    return True


def check_database():
    """Проверяет подключение к базе данных"""
    print("2. Проверка базы данных...")
    try:
        from database.connection import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Проверяем таблицы
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name IN ('users', 'jobs')
        """)
        tables = cursor.fetchall()
        
        if len(tables) != 2:
            print("   ✗ Таблицы не созданы")
            print("   → Запустите: python database/db_init.py")
            cursor.close()
            conn.close()
            return False
        
        cursor.close()
        conn.close()
        print("   ✓ База данных доступна и настроена")
        return True
    except Exception as e:
        print(f"   ✗ Ошибка подключения: {e}")
        print("   → Проверьте:")
        print("     - PostgreSQL запущен (brew services list)")
        print("     - Пароль в .env корректен")
        print("     - База данных создана (python database/db_init.py)")
        return False


def check_directories():
    """Проверяет наличие необходимых директорий"""
    print("3. Проверка директорий...")
    dirs = ['fonts', 'generated', 'logs']
    all_ok = True
    
    for dir_name in dirs:
        if not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
            print(f"   ✓ Создана директория: {dir_name}")
        else:
            print(f"   ✓ Директория существует: {dir_name}")
    
    return True


def check_dependencies():
    """Проверяет установленные зависимости"""
    print("4. Проверка зависимостей...")
    required = ['aiogram', 'reportlab', 'PIL', 'psycopg2', 'dotenv']
    missing = []
    
    for module in required:
        try:
            if module == 'PIL':
                __import__('PIL')
            elif module == 'dotenv':
                __import__('dotenv')
            else:
                __import__(module)
        except ImportError:
            missing.append(module)
    
    if missing:
        print(f"   ✗ Отсутствуют модули: {', '.join(missing)}")
        print("   → Установите: pip install -r requirements.txt")
        return False
    
    print("   ✓ Все зависимости установлены")
    return True


def main():
    """Основная функция проверки"""
    print("🔍 Проверка готовности бота к запуску...\n")
    
    checks = [
        check_env_file(),
        check_dependencies(),
        check_database(),
        check_directories(),
    ]
    
    print()
    if all(checks):
        print("✅ Все проверки пройдены! Бот готов к запуску.")
        print("   Запуск: python bot.py")
        return 0
    else:
        print("❌ Обнаружены проблемы. Исправьте их перед запуском.")
        return 1


if __name__ == "__main__":
    sys.exit(main())


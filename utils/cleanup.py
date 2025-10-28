"""Утилиты для очистки старых файлов"""
import os
import time
import logging
from config import GENERATED_DIR

logger = logging.getLogger(__name__)


def cleanup_old_pdfs(days_old: int = 7):
    """
    Удаляет PDF старше N дней
    
    Args:
        days_old: Количество дней, после которых файл считается старым
        
    Returns:
        Количество удаленных файлов
    """
    if not os.path.exists(GENERATED_DIR):
        return 0
    
    cutoff_time = time.time() - (days_old * 24 * 60 * 60)
    deleted_count = 0
    total_size_freed = 0
    
    try:
        for filename in os.listdir(GENERATED_DIR):
            if filename.endswith('.pdf'):
                file_path = os.path.join(GENERATED_DIR, filename)
                try:
                    file_mtime = os.path.getmtime(file_path)
                    if file_mtime < cutoff_time:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_count += 1
                        total_size_freed += file_size
                except OSError as e:
                    logger.warning(f"Не удалось удалить {filename}: {e}")
                except Exception as e:
                    logger.error(f"Ошибка при обработке {filename}: {e}")
        
        if deleted_count > 0:
            size_mb = total_size_freed / (1024 * 1024)
            logger.info(f"Очистка: удалено {deleted_count} PDF файлов, освобождено {size_mb:.2f} MB")
        
        return deleted_count
    except Exception as e:
        logger.error(f"Ошибка очистки старых файлов: {e}")
        return 0


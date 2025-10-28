"""Метрики производительности"""
from collections import defaultdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Metrics:
    """Класс для сбора метрик производительности"""
    
    def __init__(self):
        self.pdf_generation_times = []
        self.request_counts = defaultdict(int)
        self.error_counts = defaultdict(int)
        self.total_pdfs = 0
        
    def record_pdf_time(self, duration_ms: int):
        """Записывает время генерации PDF"""
        self.pdf_generation_times.append(duration_ms)
        self.total_pdfs += 1
        
        # Храним только последние 100 значений
        if len(self.pdf_generation_times) > 100:
            self.pdf_generation_times = self.pdf_generation_times[-100:]
    
    def record_request(self, user_id: int = None):
        """Записывает запрос"""
        if user_id:
            self.request_counts[user_id] += 1
    
    def record_error(self, error_type: str = "unknown"):
        """Записывает ошибку"""
        self.error_counts[error_type] += 1
    
    def get_stats(self) -> dict:
        """Возвращает статистику"""
        if not self.pdf_generation_times:
            return {
                "avg_time_ms": 0,
                "min_time_ms": 0,
                "max_time_ms": 0,
                "total_pdfs": self.total_pdfs,
                "total_requests": sum(self.request_counts.values()),
                "total_errors": sum(self.error_counts.values()),
                "error_breakdown": dict(self.error_counts)
            }
        
        return {
            "avg_time_ms": round(sum(self.pdf_generation_times) / len(self.pdf_generation_times), 2),
            "min_time_ms": min(self.pdf_generation_times),
            "max_time_ms": max(self.pdf_generation_times),
            "total_pdfs": self.total_pdfs,
            "total_requests": sum(self.request_counts.values()),
            "total_errors": sum(self.error_counts.values()),
            "error_breakdown": dict(self.error_counts),
            "last_100_avg": round(sum(self.pdf_generation_times[-100:]) / min(100, len(self.pdf_generation_times)), 2) if self.pdf_generation_times else 0
        }
    
    def log_stats(self):
        """Выводит статистику в лог"""
        stats = self.get_stats()
        logger.info("📊 Статистика производительности:")
        logger.info(f"   Всего PDF сгенерировано: {stats['total_pdfs']}")
        logger.info(f"   Всего запросов: {stats['total_requests']}")
        logger.info(f"   Среднее время генерации: {stats['avg_time_ms']}ms")
        logger.info(f"   Минимум: {stats['min_time_ms']}ms, Максимум: {stats['max_time_ms']}ms")
        if stats['total_errors'] > 0:
            logger.warning(f"   Ошибок: {stats['total_errors']} ({stats['error_breakdown']})")
        return stats


# Глобальный экземпляр метрик
metrics = Metrics()


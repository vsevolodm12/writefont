"""Rate limiting для защиты от спама"""
from collections import defaultdict
from datetime import datetime, timedelta

# Хранение: user_id -> [timestamp1, timestamp2, ...]
_user_requests = defaultdict(list)

# Лимиты
MAX_REQUESTS_PER_MINUTE = 10
MAX_REQUESTS_PER_HOUR = 50


def check_rate_limit(user_id: int) -> tuple[bool, str]:
    """
    Проверяет rate limit для пользователя
    
    Args:
        user_id: ID пользователя Telegram
        
    Returns:
        (allowed, message) - разрешено ли действие и сообщение об ошибке
    """
    now = datetime.now()
    
    # Очищаем старые записи (старше часа)
    user_requests = _user_requests[user_id]
    user_requests[:] = [req for req in user_requests 
                       if now - req < timedelta(hours=1)]
    
    # Проверяем лимит на минуту
    recent_minute = [req for req in user_requests 
                    if now - req < timedelta(minutes=1)]
    if len(recent_minute) >= MAX_REQUESTS_PER_MINUTE:
        return False, "⚠️ Слишком много запросов! Подождите минуту перед следующим PDF."
    
    # Проверяем лимит на час
    if len(user_requests) >= MAX_REQUESTS_PER_HOUR:
        return False, "⚠️ Превышен лимит запросов на час (50 PDF). Попробуйте позже."
    
    # Добавляем текущий запрос
    user_requests.append(now)
    return True, ""


def get_user_stats(user_id: int) -> dict:
    """Возвращает статистику запросов пользователя"""
    now = datetime.now()
    user_requests = _user_requests[user_id]
    
    # Очищаем старые
    user_requests[:] = [req for req in user_requests 
                       if now - req < timedelta(hours=1)]
    
    recent_minute = [req for req in user_requests 
                    if now - req < timedelta(minutes=1)]
    
    return {
        "requests_last_minute": len(recent_minute),
        "requests_last_hour": len(user_requests),
        "limit_per_minute": MAX_REQUESTS_PER_MINUTE,
        "limit_per_hour": MAX_REQUESTS_PER_HOUR
    }


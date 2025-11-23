"""Кэш для зарегистрированных шрифтов"""
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
import re

# Кэш: font_path -> font_name
_font_cache = {}


def get_cached_font_name(font_path: str) -> str:
    """
    Получает имя шрифта из кэша или регистрирует новый
    
    Args:
        font_path: Путь к файлу шрифта
        
    Returns:
        Имя зарегистрированного шрифта
    """
    if not font_path or not os.path.exists(font_path):
        raise FileNotFoundError(f"Шрифт не найден: {font_path}")
    
    # Проверяем кэш
    if font_path in _font_cache:
        return _font_cache[font_path]
    
    # Генерируем имя шрифта из имени файла
    font_name = os.path.basename(font_path).replace('.ttf', '')
    font_name = font_name.replace('.TTF', '')
    font_name = re.sub(r'[^a-zA-Z0-9_]', '_', font_name)
    
    # Регистрируем шрифт
    try:
        pdfmetrics.registerFont(TTFont(font_name, font_path))
        _font_cache[font_path] = font_name
        return font_name
    except Exception as e:
        raise Exception(f"Ошибка регистрации шрифта: {str(e)}")


def clear_font_cache():
    """Очищает кэш шрифтов"""
    global _font_cache
    _font_cache.clear()


def get_cache_stats():
    """Возвращает статистику кэша"""
    return {
        "cached_fonts": len(_font_cache),
        "font_paths": list(_font_cache.keys())
    }


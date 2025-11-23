"""
Модуль генерации PDF-конспектов
"""

from reportlab.lib.pagesizes import A4, A5
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from config import FONTS_DIR, GENERATED_DIR
import os
import re
import random
import unicodedata
from typing import Optional, Dict, List
def _is_cyrillic(char: str) -> bool:
    try:
        return "CYRILLIC" in unicodedata.name(char)
    except ValueError:
        return False


def _is_latin(char: str) -> bool:
    try:
        return "LATIN" in unicodedata.name(char)
    except ValueError:
        return False


class FontSelector:
    def __init__(self, font_sets, font_name_map):
        self.font_name_map = font_name_map
        self.base_meta = font_sets.get("base")
        self.base_font_name = None
        if self.base_meta and self.base_meta.get("path") in font_name_map:
            self.base_font_name = font_name_map[self.base_meta["path"]]
        self.default_font_name = self.base_font_name or (next(iter(font_name_map.values())) if font_name_map else None)

        self.cyrillic_fonts = self._prepare_fonts(font_sets.get("cyrillic", []))
        self.latin_fonts = self._prepare_fonts(font_sets.get("latin", []), include_base=False)
        self.digit_fonts = self._prepare_fonts(font_sets.get("digits", []), include_base=False)
        self.other_fonts = self._prepare_fonts(font_sets.get("other", []), include_base=False)

    def _prepare_fonts(self, records, include_base: bool = True):
        unique = []
        seen = set()
        candidates = []
        if include_base and self.base_meta:
            candidates.append(self.base_meta)
        candidates.extend(records or [])
        for record in candidates:
            if not record:
                continue
            path = record.get("path")
            if not path or path not in self.font_name_map:
                continue
            if path in seen:
                continue
            seen.add(path)
            unique.append(record)
        return unique

    def _font_supports_char(self, font_name: Optional[str], char: str) -> bool:
        """Проверяет, поддерживает ли шрифт символ"""
        if not font_name or not char:
            return False
        try:
            # Пробуем получить ширину символа - если символ не поддерживается, будет исключение
            width = pdfmetrics.stringWidth(char, font_name, 12)
            # Если ширина 0 для видимого символа (не пробел), возможно символ не поддерживается
            # Но для пробелов и некоторых специальных символов это нормально
            if width == 0 and not char.isspace():
                # Дополнительная проверка: пробуем нарисовать текст и проверить результат
                # Но это слишком сложно, поэтому просто считаем что если stringWidth не выбросил исключение,
                # то символ поддерживается
                pass
            return True
        except KeyError:
            # KeyError - шрифт не зарегистрирован или символ не поддерживается
            return False
        except (ValueError, TypeError, AttributeError):
            # Другие ошибки - возможно символ не поддерживается
            return False
        except Exception as e:
            # На всякий случай ловим все остальные исключения
            # Но для отладки можно залогировать
            return False

    def _choose_from_pool(self, char, used_fonts_per_char, pool, requirement, allow_base_fallback=True):
        candidates = [rec for rec in pool if rec and requirement(rec)]
        if allow_base_fallback and self.base_meta and requirement(self.base_meta):
            if self.base_meta not in candidates:
                candidates.append(self.base_meta)

        candidates = [rec for rec in candidates if rec and rec.get("path") in self.font_name_map]
        if char:
            supported_candidates = [
                rec for rec in candidates if self._font_supports_char(self.font_name_map[rec["path"]], char)
            ]
            if supported_candidates:
                candidates = supported_candidates

        if not candidates:
            if allow_base_fallback and self.base_font_name:
                if not char or self._font_supports_char(self.base_font_name, char):
                    return self.base_font_name
            if self.default_font_name and self._font_supports_char(self.default_font_name, char):
                return self.default_font_name
            return self.base_font_name or self.default_font_name

        used = set(used_fonts_per_char.get(char, []))
        available = [rec for rec in candidates if self.font_name_map[rec["path"]] not in used]
        if not available:
            available = candidates
        chosen = random.choice(available)
        return self.font_name_map[chosen["path"]]

    def select(self, char: Optional[str], used_fonts_per_char: dict) -> str:
        if not char or char.isspace():
            return self.base_font_name or self.default_font_name

        if char.isdigit():
            return self._choose_from_pool(
                char,
                used_fonts_per_char,
                self.digit_fonts,
                lambda rec: rec.get("supports_digits"),
            )

        if _is_cyrillic(char):
            if char.isupper():
                requirement = lambda rec: rec.get("supports_cyrillic_upper")
            else:
                requirement = lambda rec: rec.get("supports_cyrillic_lower")
            return self._choose_from_pool(
                char,
                used_fonts_per_char,
                self.cyrillic_fonts,
                requirement,
            )

        if _is_latin(char):
            if char.isupper():
                requirement = lambda rec: rec.get("supports_latin_upper")
            else:
                requirement = lambda rec: rec.get("supports_latin_lower")
            return self._choose_from_pool(
                char,
                used_fonts_per_char,
                self.latin_fonts,
                requirement,
            )

        # Пунктуация и прочие символы
        if unicodedata.category(char).startswith(("P", "S")):
            # Проверяем шрифты в порядке приоритета:
            # 1. Шрифты с цифрами (часто содержат пунктуацию)
            # 2. Базовый шрифт
            # 3. Остальные шрифты
            # 4. Default шрифт
            
            # Сначала проверяем шрифты с цифрами (они часто содержат пунктуацию)
            for rec in self.digit_fonts:
                font_name = self.font_name_map.get(rec.get("path"))
                if font_name and self._font_supports_char(font_name, char):
                    return font_name
            
            # Затем базовый шрифт
            if self.base_meta and self.base_meta.get("path") in self.font_name_map:
                base_font_name = self.font_name_map[self.base_meta["path"]]
                if base_font_name and self._font_supports_char(base_font_name, char):
                    return base_font_name
            
            # Затем остальные шрифты
            other_fonts = self.cyrillic_fonts + self.latin_fonts + self.other_fonts
            for rec in other_fonts:
                font_name = self.font_name_map.get(rec.get("path"))
                if font_name and self._font_supports_char(font_name, char):
                    return font_name
            
            # Если ничего не подошло, пробуем default
            if self.default_font_name and self._font_supports_char(self.default_font_name, char):
                return self.default_font_name
            
            # В крайнем случае возвращаем базовый (даже если он не поддерживает)
            return self.base_font_name or self.default_font_name

        return self.base_font_name or self.default_font_name


def register_font(font_path: str):
    """Регистрирует пользовательский шрифт в ReportLab (использует кэш)"""
    # Используем кэширование шрифтов для производительности
    from utils.font_cache import get_cached_font_name
    
    if not font_path:
        raise ValueError("Путь к шрифту не указан")
    
    if not os.path.exists(font_path):
        raise FileNotFoundError(f"Шрифт не найден: {font_path}")
    
    if not os.path.isfile(font_path):
        raise ValueError(f"Указанный путь не является файлом: {font_path}")
    
    # Проверка расширения файла
    valid_extensions = ['.ttf', '.TTF']
    if not any(font_path.endswith(ext) for ext in valid_extensions):
        raise ValueError(f"Неподдерживаемый формат шрифта. Используйте .ttf")
    
    # Используем кэшированный шрифт
    try:
        font_name = get_cached_font_name(font_path)
        return font_name
    except Exception as e:
        raise Exception(f"Ошибка регистрации шрифта: {str(e)}")


def draw_formatted_text(c, x, y, text, font_name, font_size, bold=False, italic=False, underline=False):
    """
    Рисует текст с форматированием (жирный, курсив, подчеркнутый)
    """
    c.setFont(font_name, font_size)
    
    # Для жирного - рисуем дважды со смещением (имитация жирного)
    if bold:
        c.drawString(x + 0.4, y, text)
        c.drawString(x, y, text)
    else:
        c.drawString(x, y, text)
    
    # Для подчеркнутого - рисуем линию под текстом
    if underline:
        text_width = c.stringWidth(text, font_name, font_size)
        line_y = y - 1.5
        c.setLineWidth(0.7)
        c.setStrokeColor(colors.black)
        c.line(x, line_y, x + text_width, line_y)


def safe_draw_string(c, x, y, text, font_size, select_font):
    """
    Безопасно рисует строку, используя TextObject для лучшей поддержки Unicode.
    select_font — функция, возвращающая имя шрифта для конкретного символа.
    """
    clean_text = text
    clean_text = re.sub(r'\*\*(.*?)\*\*', r'\1', clean_text)
    clean_text = re.sub(r'__(.*?)__', r'\1', clean_text)
    clean_text = re.sub(r'~~(.*?)~~', r'\1', clean_text)
    clean_text = re.sub(r'\*(.*?)\*', r'\1', clean_text)
    clean_text = re.sub(r'_(.*?)_', r'\1', clean_text)

    if select_font:
        current_x = x
        t = c.beginText(current_x, y)

        words = re.split(r'(\W)', clean_text)

        for word in words:
            if not word:
                continue

            if not word.strip():
                font_name = select_font(" ", {})
                t.setFont(font_name, font_size)
                t.textOut(word)
                continue

            used_fonts_per_char = {}

            for char in word:
                font_name = select_font(char, used_fonts_per_char)
                if char not in used_fonts_per_char:
                    used_fonts_per_char[char] = []
                used_fonts_per_char[char].append(font_name)
                t.setFont(font_name, font_size)
                t.textOut(char)

        c.drawText(t)
    else:
        t = c.beginText(x, y)
        default_font = select_font(None, {}) if select_font else None
        if default_font:
            t.setFont(default_font, font_size)
        t.textOut(clean_text)
        c.drawText(t)


def draw_line_with_formatting(c, x, y, line_text, font_size, selector):
    """
    Рисует строку текста с поддержкой форматирования
    """
    # Убираем разметку для рисования
    clean_text = line_text
    clean_text = re.sub(r'\*\*(.*?)\*\*', r'\1', clean_text)
    clean_text = re.sub(r'__(.*?)__', r'\1', clean_text)
    clean_text = re.sub(r'~~(.*?)~~', r'\1', clean_text)
    clean_text = re.sub(r'\*(.*?)\*', r'\1', clean_text)
    clean_text = re.sub(r'_(.*?)_', r'\1', clean_text)
    
    # Используем TextObject для рисования
    # Важно: используем textOut, а не textLine, чтобы избежать автоматического переноса строки
    # (textLine автоматически вычитает leading, что создает лишний интервал)
    base_font_name = selector.base_font_name or selector.default_font_name
    if not base_font_name:
        raise ValueError("Невозможно определить базовый шрифт для форматирования текста")

    safe_draw_string(c, x, y, clean_text, font_size, selector.select)
    
    # Проверяем есть ли подчеркнутые части в строке для рисования линии
    underline_pattern = r'~~(.*?)~~'
    for match in re.finditer(underline_pattern, line_text):
        start_text = line_text[:match.start()]
        underline_text = match.group(1)
        
        # Убираем разметку для вычисления ширины
        start_clean = re.sub(r'\*\*|__|\*|_|~~', '', start_text)
        underline_clean = re.sub(r'\*\*|__|\*|_|~~', '', underline_text)
        
        # Вычисляем позицию подчеркнутого текста
        c.setFont(base_font_name, font_size)
        start_width = c.stringWidth(start_clean, base_font_name, font_size)
        underline_width = c.stringWidth(underline_clean, base_font_name, font_size)
        
        # Рисуем линию под текстом
        line_y = y - 1.5
        c.setLineWidth(0.7)
        c.setStrokeColor(colors.black)
        c.line(x + start_width, line_y, x + start_width + underline_width, line_y)


def get_actual_cell_height(page_size, cell_size=5*mm, margin=15*mm):
    """
    Вычисляет реальную высоту клетки для выравнивания текста
    """
    from reportlab.lib.units import mm
    
    width, height = page_size
    work_height = height - 2 * margin
    num_horizontal_cells = int(work_height / cell_size)
    return work_height / float(num_horizontal_cells) if num_horizontal_cells > 0 else cell_size


def get_page_margins(page_number: int, first_page_side: str, cell_size, grid_enabled: bool, margin_default, page_format: str = None):
    """
    Возвращает отступы для страницы с учетом зеркальных полей для тетради.
    
    Args:
        page_number: Номер страницы (1, 2, 3...)
        first_page_side: 'left' или 'right' - сторона первой страницы
        cell_size: Размер клетки
        grid_enabled: Включена ли сетка
        margin_default: Дефолтный отступ
        page_format: Формат страницы ('A4' или 'A5')
    
    Returns:
        (left_margin, right_margin) - отступы слева и справа
    """
    # Определяем, какая страница по факту (левая или правая в тетради)
    # Если first_page_side = 'right', то:
    #   страница 1 = правая (больший отступ слева)
    #   страница 2 = левая (меньший отступ слева)
    #   страница 3 = правая
    # Если first_page_side = 'left', то наоборот
    
    if first_page_side == 'right':
        # Первая страница правая, вторая левая, третья правая...
        is_right_page = (page_number % 2) == 1
    else:  # first_page_side == 'left'
        # Первая страница левая, вторая правая, третья левая...
        is_right_page = (page_number % 2) == 0
    
    if grid_enabled:
        # Для тетради с клеткой
        if is_right_page:
            # Правая страница: больший отступ слева (чтобы не попасть под кольца)
            # Уменьшаем на 1 клетку для смещения текста влево (только для формата с клеткой, не A4)
            if page_format and page_format != 'A4':
                left_margin = 4 * cell_size - cell_size  # 15mm (было 20mm) - смещение на 1 клетку влево
            else:
                left_margin = 4 * cell_size  # 20mm - без смещения для A4
            right_margin = 2 * cell_size  # 10mm
        else:
            # Левая страница: меньший отступ слева, больший справа
            left_margin = 2 * cell_size  # 10mm
            right_margin = 4 * cell_size  # 20mm
    else:
        # Без сетки: используем пропорциональные отступы
        if is_right_page:
            left_margin = margin_default * 1.5
            right_margin = margin_default
        else:
            left_margin = margin_default
            right_margin = margin_default * 1.5
    
    return left_margin, right_margin


def generate_grid_background(c, page_size, cell_size=5*mm, margin=15*mm):
    """
    Генерирует фоновую сетку (клетку) как в тетради.
    Сетка всегда начинается от краев margin и полностью заполняет рабочую область.
    Использует динамическое вычисление количества клеток на основе реальных размеров.
    """
    from reportlab.lib.pagesizes import A4, A5
    
    width, height = page_size
    
    # Вычисляем рабочую область (от margin до margin)
    work_width = width - 2 * margin
    work_height = height - 2 * margin
    
    # Вычисляем количество клеток (округляем вниз, чтобы не выходить за границы)
    # Это детерминированно для одинаковых форматов
    num_vertical_cells = int(work_width / cell_size)
    num_horizontal_cells = int(work_height / cell_size)
    
    # Вычисляем реальный размер клетки для полного заполнения рабочей области
    # Растягиваем клетки чтобы сетка точно заполняла work_width x work_height
    # Это гарантирует что сетка дойдет до самых краев
    actual_cell_width = work_width / float(num_vertical_cells) if num_vertical_cells > 0 else cell_size
    actual_cell_height = work_height / float(num_horizontal_cells) if num_horizontal_cells > 0 else cell_size
    
    # Начальные координаты сетки (ровно на margin)
    grid_start_x = margin
    grid_start_y = margin
    
    # Конечные координаты сетки (ровно на противоположном margin)
    # Используем точные значения work_width и work_height для гарантии
    grid_end_x = margin + work_width
    grid_end_y = margin + work_height
    
    # Рисуем вертикальные линии (включая первую и последнюю)
    c.setStrokeColor(colors.Color(0.9, 0.9, 0.9))
    c.setLineWidth(0.3)
    
    # Рисуем вертикальные линии от первой до последней
    # Первая линия на grid_start_x, последняя на grid_end_x
    for i in range(num_vertical_cells + 1):
        # Вычисляем позицию линии так, чтобы первая была на grid_start_x,
        # а последняя точно на grid_end_x
        if num_vertical_cells > 0:
            if i == num_vertical_cells:
                # Последняя линия точно на grid_end_x
                x = grid_end_x
            else:
                x = grid_start_x + (i * actual_cell_width)
        else:
            x = grid_start_x
        # Линии рисуются от верхней границы до нижней границы (полная высота)
        c.line(x, grid_start_y, x, grid_end_y)
    
    # Рисуем горизонтальные линии (включая первую и последнюю)
    for i in range(num_horizontal_cells + 1):
        # Вычисляем позицию линии так, чтобы первая была на grid_start_y,
        # а последняя точно на grid_end_y
        if num_horizontal_cells > 0:
            if i == num_horizontal_cells:
                # Последняя линия точно на grid_end_y
                y = grid_end_y
            else:
                y = grid_start_y + (i * actual_cell_height)
        else:
            y = grid_start_y
        # Линии рисуются от левой границы до правой границы (полная ширина)
        c.line(grid_start_x, y, grid_end_x, y)


def _is_list_item(text: str) -> bool:
    """
    Проверяет, является ли текст элементом списка (начинается с bullet point).
    
    Args:
        text: Текст для проверки
        
    Returns:
        True если текст начинается с bullet point (•), False иначе
    """
    if not text:
        return False
    stripped = text.strip()
    # Проверяем различные варианты bullet points
    return stripped.startswith('•') or stripped.startswith('*') or stripped.startswith('-') or stripped.startswith('—')


def generate_pdf(text_content: str, font_sets: Dict[str, list], page_format: str, output_path: str, grid_enabled: bool = False, first_page_side: str = 'right'):
    """
    Генерирует PDF с текстом используя наборы шрифтов разных типов.

    Args:
        text_content: Текст для размещения.
        font_sets: Словарь с наборами шрифтов и их метаданными.
        page_format: Формат страницы ('A4' или 'A5').
        output_path: Путь для сохранения PDF файла.
        grid_enabled: Включить фоновую сетку.
        first_page_side: 'left' или 'right' - сторона первой страницы для зеркальных отступов.
    """
    # Проверка текста
    if not text_content or not text_content.strip():
        raise ValueError("Текст не может быть пустым")
    
    # Проверка формата страницы
    if page_format not in ['A4', 'A5']:
        raise ValueError(f"Неподдерживаемый формат страницы: {page_format}. Используйте 'A4' или 'A5'")
    
    base_meta = font_sets.get("base")
    if not base_meta or not base_meta.get("path"):
        raise ValueError("Не найден базовый шрифт для генерации PDF")

    font_names = {}
    for record in font_sets.get("all", []):
        path = record.get("path")
        if path and path not in font_names:
            font_names[path] = register_font(path)
    base_path = base_meta.get("path")
    if base_path and base_path not in font_names:
        font_names[base_path] = register_font(base_path)

    selector = FontSelector(font_sets, font_names)
    base_font_name = selector.base_font_name or selector.default_font_name
    if not base_font_name:
        raise ValueError("Не удалось подготовить шрифты для генерации PDF")
    
    # Определяем размеры страницы
    if page_format == 'A5':
        page_size = A5
    else:  # A4
        page_size = A4
    
    # Создаем PDF
    c = canvas.Canvas(output_path, pagesize=page_size)
    
    # Настройки страницы
    width, height = page_size
    margin_default = 15 * mm
    bottom_margin = 8 * mm  # Уменьшенный нижний отступ для использования большего пространства
    cell_size = 5 * mm  # Базовый размер клетки сетки
    grid_margin = 0 if grid_enabled else margin_default
    
    # Вычисляем реальную высоту клетки (для всех режимов для единообразия)
    actual_cell_height = get_actual_cell_height(page_size, cell_size, margin=grid_margin if grid_enabled else margin_default)
    
    # Единые параметры текста для всех режимов (A4, A5, с клеткой и без)
    # Размер шрифта увеличен в 2 раза
    font_size = 32
    
    # Межстрочный интервал: 1 клетка для текста + 1 клетка для пробела = 2 клетки
    # Используем actual_cell_height для точного соответствия (даже без сетки)
    line_height = 2 * actual_cell_height

    # Небольшое смещение вниз, чтобы текст был ближе к нижней части клетки
    baseline_offset = actual_cell_height * 0.25
    
    # Отступ между абзацами: 2 клетки
    paragraph_spacing = 2 * actual_cell_height
    
    # Функция для получения отступов страницы
    def get_current_page_margins():
        page_num = c.getPageNumber()
        return get_page_margins(page_num, first_page_side, cell_size, grid_enabled, margin_default, page_format)
    
    # Функция для получения начальной Y позиции при создании новой страницы
    def get_initial_y():
        if grid_enabled:
            grid_start_y = grid_margin
            # Определяем, какая страница (правая или левая) для выравнивания текста
            page_num = c.getPageNumber()
            if first_page_side == 'right':
                is_right_page = (page_num % 2) == 1
            else:
                is_right_page = (page_num % 2) == 0
            
            # Для обеих страниц используем одинаковый отступ (2 клетки)
            first_text_cell_index = 2
            # Вычисляем позицию Y от низа страницы (в ReportLab координаты снизу вверх)
            distance_from_top = grid_start_y + (first_text_cell_index + 1) * actual_cell_height
            return height - distance_from_top - baseline_offset
        else:
            return height - margin_default - baseline_offset
    
    # Функция для получения начальной X позиции (левый отступ) для текущей страницы
    def get_initial_x():
        left_margin, _ = get_current_page_margins()
        return left_margin
    
    # Рисуем сетку если нужно (ДО текста, чтобы она была фоном)
    if grid_enabled:
        generate_grid_background(c, page_size, cell_size, margin=grid_margin)
        
        # Привязка к низу клетки: начинаем с первой строки текста
        # В ReportLab координаты идут снизу вверх, поэтому вычисляем от низа страницы
        # Отступ сверху = 2 клетки для обеих страниц
        grid_start_y = grid_margin  # это отступ от верха
        # Определяем, какая страница (правая или левая) для выравнивания текста
        page_num = c.getPageNumber()
        if first_page_side == 'right':
            is_right_page = (page_num % 2) == 1
        else:
            is_right_page = (page_num % 2) == 0
        
        # Для обеих страниц используем одинаковый отступ (2 клетки)
        first_text_cell_index = 2
        # Вычисляем позицию Y от низа страницы (в ReportLab координаты снизу вверх)
        # Расстояние от верха = margin + (first_text_cell_index + 1) * actual_cell_height
        distance_from_top = grid_start_y + (first_text_cell_index + 1) * actual_cell_height
        y = height - distance_from_top - baseline_offset  # Y координата от низа страницы
        
        x = get_initial_x()  # Используем зеркальные отступы
    else:
        # Без сетки: начинаем с отступа сверху, но используем те же параметры текста
        y = height - margin_default - baseline_offset
        x = get_initial_x()  # Используем зеркальные отступы
    
    # Обрабатываем текст: разбиваем на абзацы
    # Поддерживаем обычные переносы строк как абзацы
    paragraphs = re.split(r'\n\s*\n|\n(?=\S)', text_content)
    
    first_line_in_paragraph = True
    prev_was_list_item = False  # Отслеживаем, был ли предыдущий абзац элементом списка
    
    for i, paragraph in enumerate(paragraphs):
        if not paragraph.strip():
            y -= paragraph_spacing
            prev_was_list_item = False
            continue
        
        paragraph_text = paragraph.strip()
        is_list_item = _is_list_item(paragraph_text)
        
        # Определяем, является ли следующий абзац элементом списка
        next_is_list_item = False
        if i + 1 < len(paragraphs):
            next_paragraph = paragraphs[i + 1].strip()
            if next_paragraph:
                next_is_list_item = _is_list_item(next_paragraph)
        
        # Парсим форматирование (жирный, курсив, подчеркнутый)
        # Используем Markdown синтаксис: **жирный**, *курсив*, ~~подчеркнутый~~
        # Но упрощаем - просто удаляем разметку для вариативных шрифтов
        # И используем вариативные символы
        
        # Разбиваем абзац на строки (учитываем обычные переносы строк)
        paragraph_lines = paragraph_text.split('\n')
        
        for para_line in paragraph_lines:
            if not para_line.strip():
                y -= line_height
                continue
            
            # Обрабатываем форматирование Markdown
            # Поддерживаем: **жирный**, *курсив*, ~~подчеркнутый~~
            # Парсим форматирование по частям для правильного отображения
            parts = []
            text = para_line
            i = 0
            
            while i < len(text):
                # Проверяем жирный **text** или __text__
                bold_match = re.match(r'\*\*(.*?)\*\*|__(.*?)__', text[i:])
                if bold_match:
                    content = bold_match.group(1) or bold_match.group(2)
                    parts.append({'text': content, 'bold': True, 'underline': False})
                    i += bold_match.end()
                    continue
                
                # Проверяем подчеркнутый ~~text~~
                underline_match = re.match(r'~~(.*?)~~', text[i:])
                if underline_match:
                    content = underline_match.group(1)
                    parts.append({'text': content, 'bold': False, 'underline': True})
                    i += underline_match.end()
                    continue
                
                # Проверяем курсив *text* или _text_
                italic_match = re.match(r'\*(.*?)\*|_(.*?)_', text[i:])
                if italic_match and not text[i:italic_match.end()].startswith('**') and not text[i:italic_match.end()].startswith('~~'):
                    # Пропускаем курсив (просто убираем разметку)
                    content = italic_match.group(1) or italic_match.group(2)
                    parts.append({'text': content, 'bold': False, 'underline': False})
                    i += italic_match.end()
                    continue
                
                # Обычный текст
                parts.append({'text': text[i], 'bold': False, 'underline': False})
                i += 1
            
            # Объединяем части в одну строку для обработки (форматирование обрабатывается при рисовании)
            clean_line = ''.join([p['text'] for p in parts])
            
            # Разбиваем на слова и применяем вариативность
            words = clean_line.split()
            current_line = []
            current_width = 0
            # Доступная ширина текста с учетом левого и правого отступов
            _, right_margin = get_current_page_margins()
            max_width = width - x - right_margin
            effective_max_width = max_width
            
            for word in words:
                word_width = c.stringWidth(word + ' ', base_font_name, font_size)
                single_word_width = c.stringWidth(word, base_font_name, font_size)
                
                # Если одно слово шире страницы, разбиваем на части
                if single_word_width > effective_max_width:
                    if current_line:
                        current_x = x
                        words_line = ' '.join(current_line)
                        
                        # Проверяем, достаточно ли места для строки ПЕРЕД рисованием
                        if y < bottom_margin + line_height:
                            c.showPage()
                            if grid_enabled:
                                generate_grid_background(c, page_size, cell_size, margin=grid_margin)
                            y = get_initial_y()
                            x = get_initial_x()  # Обновляем x для новой страницы
                            _, right_margin = get_current_page_margins()
                            max_width = width - x - right_margin
                            effective_max_width = max_width
                        
                        # Рисуем с форматированием
                        draw_line_with_formatting(c, current_x, y, words_line, font_size, selector)
                        # Переходим к следующей строке: вычитаем line_height (двигаемся вниз)
                        y -= line_height
                        
                        current_line = []
                        current_width = 0
                        first_line_in_paragraph = False
                        effective_max_width = max_width
                    
                    # Разбиваем длинное слово посимвольно
                    chars = list(word)
                    temp_word = ''
                    for char in chars:
                        char_width = c.stringWidth(temp_word + char, base_font_name, font_size)
                        if char_width <= effective_max_width:
                            temp_word += char
                        else:
                            if temp_word:
                                if y < bottom_margin + line_height:
                                    c.showPage()
                                    if grid_enabled:
                                        generate_grid_background(c, page_size, cell_size, margin=grid_margin)
                                    y = get_initial_y()
                                    x = get_initial_x()  # Обновляем x для новой страницы
                                    _, right_margin = get_current_page_margins()
                                    max_width = width - x - right_margin
                                    effective_max_width = max_width
                                
                                current_x = x
                                safe_draw_string(c, current_x, y, temp_word, font_size, selector.select)
                                y -= line_height
                                first_line_in_paragraph = False
                                effective_max_width = max_width
                            temp_word = char
                    if temp_word:
                        if y < bottom_margin + line_height:
                            c.showPage()
                            if grid_enabled:
                                generate_grid_background(c, page_size, cell_size, margin=grid_margin)
                            y = get_initial_y()
                            x = get_initial_x()  # Обновляем x для новой страницы
                            _, right_margin = get_current_page_margins()
                            max_width = width - x - right_margin
                            effective_max_width = max_width
                        
                        current_x = x
                        safe_draw_string(c, current_x, y, temp_word, font_size, selector.select)
                        y -= line_height
                        first_line_in_paragraph = False
                        effective_max_width = max_width
                    
                    current_width = 0
                elif current_width + word_width <= effective_max_width:
                    current_line.append(word)
                    current_width += word_width
                else:
                    if current_line:
                        current_x = x
                        words_line = ' '.join(current_line)
                        
                        if y < bottom_margin + line_height:
                            c.showPage()
                            if grid_enabled:
                                generate_grid_background(c, page_size, cell_size, margin=grid_margin)
                            y = get_initial_y()
                            x = get_initial_x()  # Обновляем x для новой страницы
                            _, right_margin = get_current_page_margins()
                            max_width = width - x - right_margin
                            effective_max_width = max_width
                        
                        current_x = x
                        safe_draw_string(c, current_x, y, words_line, font_size, selector.select)
                        y -= line_height
                        
                        first_line_in_paragraph = False
                        effective_max_width = max_width
                    
                    current_line = [word]
                    current_width = word_width
            
            # Рисуем последнюю строку абзаца
            if current_line:
                current_x = x
                words_line = ' '.join(current_line)
                
                if y < margin_default + line_height:
                    c.showPage()
                    if grid_enabled:
                        generate_grid_background(c, page_size, cell_size, margin=grid_margin)
                    y = get_initial_y()
                    x = get_initial_x()  # Обновляем x для новой страницы
                    _, right_margin = get_current_page_margins()
                    max_width = width - x - right_margin
                    effective_max_width = max_width
                
                current_x = x
                safe_draw_string(c, current_x, y, words_line, font_size, selector.select)
                y -= line_height
                first_line_in_paragraph = False
        
        # Отступ между абзацами
        # Если текущий и следующий абзацы - элементы списка, используем меньший интервал
        if is_list_item and next_is_list_item:
            # Для элементов списка используем только line_height (один интервал)
            y -= line_height
        else:
            # Для обычных абзацев используем полный paragraph_spacing
            y -= paragraph_spacing
        
        first_line_in_paragraph = True
        prev_was_list_item = is_list_item
    
    # Сохраняем PDF
    c.save()


def generate_pdf_for_job(job_id: int, text_content: str, font_sets: Dict[str, list], page_format: str, grid_enabled: bool = False, first_page_side: str = 'right') -> str:
    """
    Генерирует PDF для задачи из jobs таблицы
    
    Args:
        job_id: ID задачи
        text_content: Текст для генерации
        font_sets: Наборы шрифтов
        page_format: Формат страницы
        grid_enabled: Включена ли сетка
        first_page_side: 'left' или 'right' - сторона первой страницы
    
    Returns:
        Путь к созданному PDF файлу
    """
    # Проверка параметров
    if not job_id or job_id <= 0:
        raise ValueError("Некорректный ID задачи")
    
    if not text_content:
        raise ValueError("Текст не может быть пустым")
    
    base_meta = font_sets.get("base")
    if not base_meta or not base_meta.get("path"):
        raise ValueError("Базовый шрифт не указан")
    
    if not page_format:
        raise ValueError("Формат страницы не указан")
    
    os.makedirs(GENERATED_DIR, exist_ok=True)
    output_path = os.path.join(GENERATED_DIR, f"job_{job_id}.pdf")
    
    generate_pdf(text_content, font_sets, page_format, output_path, grid_enabled, first_page_side)
    
    return output_path

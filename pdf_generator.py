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
    valid_extensions = ['.ttf', '.otf', '.TTF', '.OTF']
    if not any(font_path.endswith(ext) for ext in valid_extensions):
        raise ValueError(f"Неподдерживаемый формат шрифта. Используйте .ttf или .otf")
    
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


def safe_draw_string(c, x, y, text, font_name, font_size, font_path, font_names=None):
    """
    Безопасно рисует строку, используя TextObject для лучшей поддержки Unicode
    Если font_names указан - случайно выбирает шрифт для каждой буквы
    В одном слове одинаковые буквы не будут использовать один и тот же шрифт
    """
    # Убираем символы разметки Markdown для рисования
    clean_text = text
    clean_text = re.sub(r'\*\*(.*?)\*\*', r'\1', clean_text)  # Убираем **
    clean_text = re.sub(r'__(.*?)__', r'\1', clean_text)  # Убираем __
    clean_text = re.sub(r'~~(.*?)~~', r'\1', clean_text)  # Убираем ~~
    clean_text = re.sub(r'\*(.*?)\*', r'\1', clean_text)  # Убираем *
    clean_text = re.sub(r'_(.*?)_', r'\1', clean_text)  # Убираем _
    
    # Если есть несколько шрифтов - рисуем каждую букву разным шрифтом
    if font_names and len(font_names) > 1:
        current_x = x
        t = c.beginText(current_x, y)
        
        # Разбиваем текст на слова (сохраняем пробелы и знаки препинания отдельно)
        # Используем регулярное выражение для разделения на слова и не-слова
        words = re.split(r'(\W)', clean_text)  # \W - все не-словесные символы
        
        for word in words:
            if not word or not word.strip():  # Пробелы и знаки препинания рисуем обычным способом
                if word:  # Если это не пустая строка (например, пробел или знак препинания)
                    # Для пробелов и знаков используем любой случайный шрифт
                    random_font = random.choice(list(font_names.values()))
                    t.setFont(random_font, font_size)
                    t.textOut(word)
                continue
            
            # Для каждого слова отслеживаем использованные шрифты для каждой буквы
            # Словарь: буква -> список использованных шрифтов для этой буквы в этом слове
            used_fonts_per_char = {}
            
            for char in word:
                available_fonts = list(font_names.values())
                
                # Если эта буква уже встречалась в слове, исключаем использованные шрифты
                if char in used_fonts_per_char:
                    # Получаем шрифты, которые уже использовались для этой буквы
                    used_for_this_char = used_fonts_per_char[char]
                    
                    # Исключаем использованные шрифты из доступных
                    available_fonts = [f for f in available_fonts if f not in used_for_this_char]
                    
                    # Если все шрифты уже использованы, разрешаем повторение
                    # (это может случиться если буква повторяется больше раз, чем доступно шрифтов)
                    if not available_fonts:
                        available_fonts = list(font_names.values())
                
                # Выбираем случайный шрифт из доступных
                random_font = random.choice(available_fonts)
                
                # Записываем, какой шрифт использован для этой буквы
                if char not in used_fonts_per_char:
                    used_fonts_per_char[char] = []
                used_fonts_per_char[char].append(random_font)
                
                t.setFont(random_font, font_size)
                t.textOut(char)
        
        c.drawText(t)
    else:
        # Используем TextObject - он правильно обрабатывает Unicode и пользовательские шрифты
        # textOut не добавляет автоматический перенос строки, что нам нужно
        t = c.beginText(x, y)
        t.setFont(font_name, font_size)
        t.textOut(clean_text)
        c.drawText(t)


def draw_line_with_formatting(c, x, y, line_text, font_name, font_size, font_path):
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
    t = c.beginText(x, y)
    t.setFont(font_name, font_size)
    t.textOut(clean_text)
    c.drawText(t)
    
    # Проверяем есть ли подчеркнутые части в строке для рисования линии
    underline_pattern = r'~~(.*?)~~'
    for match in re.finditer(underline_pattern, line_text):
        start_text = line_text[:match.start()]
        underline_text = match.group(1)
        
        # Убираем разметку для вычисления ширины
        start_clean = re.sub(r'\*\*|__|\*|_|~~', '', start_text)
        underline_clean = re.sub(r'\*\*|__|\*|_|~~', '', underline_text)
        
        # Вычисляем позицию подчеркнутого текста
        c.setFont(font_name, font_size)
        start_width = c.stringWidth(start_clean, font_name, font_size)
        underline_width = c.stringWidth(underline_clean, font_name, font_size)
        
        # Рисуем линию под текстом
        line_y = y - 1.5
        c.setLineWidth(0.7)
        c.setStrokeColor(colors.black)
        c.line(x + start_width, line_y, x + start_width + underline_width, line_y)


def get_actual_cell_height(page_size, cell_size=5*mm):
    """
    Вычисляет реальную высоту клетки для выравнивания текста
    """
    from reportlab.lib.units import mm
    
    width, height = page_size
    margin = 15 * mm
    work_height = height - 2 * margin
    num_horizontal_cells = int(work_height / cell_size)
    return work_height / float(num_horizontal_cells) if num_horizontal_cells > 0 else cell_size


def generate_grid_background(c, page_size, cell_size=5*mm):
    """
    Генерирует фоновую сетку (клетку) как в тетради.
    Сетка всегда начинается от краев margin и полностью заполняет рабочую область.
    Использует динамическое вычисление количества клеток на основе реальных размеров.
    """
    from reportlab.lib.pagesizes import A4, A5
    
    width, height = page_size
    margin = 15 * mm
    
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


def generate_pdf(text_content: str, font_path: str, page_format: str, output_path: str, grid_enabled: bool = False, variant_fonts: list = None):
    """
    Генерирует PDF с текстом используя пользовательский шрифт и вариативные шрифты
    
    Args:
        text_content: Текст для размещения в PDF
        font_path: Путь к основному TTF-шрифту
        page_format: Формат страницы ('A4' или 'A5')
        output_path: Путь для сохранения PDF файла
        grid_enabled: Включить фоновую сетку
        variant_fonts: Список путей к вариативным шрифтам для случайного выбора
    """
    # Проверка текста
    if not text_content or not text_content.strip():
        raise ValueError("Текст не может быть пустым")
    
    # Проверка формата страницы
    if page_format not in ['A4', 'A5']:
        raise ValueError(f"Неподдерживаемый формат страницы: {page_format}. Используйте 'A4' или 'A5'")
    
    # Подготавливаем список всех шрифтов (основной + варианты)
    all_fonts = [font_path]
    if variant_fonts:
        all_fonts.extend(variant_fonts)
    
    # Регистрируем все шрифты и получаем их имена
    font_names = {}
    for fp in all_fonts:
        font_name = register_font(fp)
        font_names[fp] = font_name
    
    # Основной шрифт используется по умолчанию
    main_font_name = font_names[font_path]
    
    # Определяем размеры страницы
    if page_format == 'A5':
        page_size = A5
    else:  # A4
        page_size = A4
    
    # Создаем PDF
    c = canvas.Canvas(output_path, pagesize=page_size)
    
    # Настройки страницы
    width, height = page_size
    margin = 15 * mm
    cell_size = 5 * mm  # Базовый размер клетки сетки
    indent_first_line = 0  # Красная строка отключена, общий левый отступ = 2 клетки
    
    # Вычисляем реальную высоту клетки (для всех режимов для единообразия)
    actual_cell_height = get_actual_cell_height(page_size, cell_size)
    
    # Единые параметры текста для всех режимов (A4, A5, с клеткой и без)
    # Размер шрифта увеличен в 2 раза
    font_size = 32
    
    # Межстрочный интервал: 1 клетка для текста + 1 клетка для пробела = 2 клетки
    # Используем actual_cell_height для точного соответствия (даже без сетки)
    line_height = 2 * actual_cell_height
    
    # Отступ между абзацами: 2 клетки
    paragraph_spacing = 2 * actual_cell_height
    
    # Рисуем сетку если нужно (ДО текста, чтобы она была фоном)
    if grid_enabled:
        generate_grid_background(c, page_size, cell_size)
        
        # Привязка к низу клетки: начинаем с первой строки текста
        # В ReportLab координаты идут снизу вверх, поэтому вычисляем от низа страницы
        # Отступ сверху = 2 клетки, затем первая клетка для текста
        grid_start_y = margin  # это отступ от верха
        first_text_cell_index = 2  # пропускаем 2 клетки сверху
        # Вычисляем позицию Y от низа страницы (в ReportLab координаты снизу вверх)
        # Расстояние от верха = margin + (first_text_cell_index + 1) * actual_cell_height
        distance_from_top = grid_start_y + (first_text_cell_index + 1) * actual_cell_height
        y = height - distance_from_top  # Y координата от низа страницы
        
        x = margin + 2 * cell_size                         # 2 клетки слева
    else:
        # Без сетки: начинаем с отступа сверху, но используем те же параметры текста
        y = height - margin
        x = margin + 2 * cell_size
    
    # Функция для получения начальной Y позиции при создании новой страницы
    def get_initial_y():
        if grid_enabled:
            grid_start_y = margin
            first_text_cell_index = 2
            # Вычисляем позицию Y от низа страницы (в ReportLab координаты снизу вверх)
            distance_from_top = grid_start_y + (first_text_cell_index + 1) * actual_cell_height
            return height - distance_from_top
        else:
            return height - margin
    
    # Обрабатываем текст: разбиваем на абзацы
    # Поддерживаем обычные переносы строк как абзацы
    paragraphs = re.split(r'\n\s*\n|\n(?=\S)', text_content)
    
    first_line_in_paragraph = True
    
    for paragraph in paragraphs:
        if not paragraph.strip():
            y -= paragraph_spacing
            continue
        
        paragraph_text = paragraph.strip()
        
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
            # Доступная ширина текста с учетом левого отступа и правого поля
            max_width = width - x - margin
            effective_max_width = max_width
            
            for word in words:
                word_width = c.stringWidth(word + ' ', font_name, font_size)
                single_word_width = c.stringWidth(word, font_name, font_size)
                
                # Если одно слово шире страницы, разбиваем на части
                if single_word_width > effective_max_width:
                    if current_line:
                        current_x = x
                        words_line = ' '.join(current_line)
                        
                        # Проверяем, достаточно ли места для строки ПЕРЕД рисованием
                        if y < margin + line_height:
                            c.showPage()
                            if grid_enabled:
                                generate_grid_background(c, page_size, cell_size)
                            y = get_initial_y()
                        
                        # Рисуем с форматированием
                        draw_line_with_formatting(c, current_x, y, words_line, font_name, font_size, font_path)
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
                        char_width = c.stringWidth(temp_word + char, font_name, font_size)
                        if char_width <= effective_max_width:
                            temp_word += char
                        else:
                            if temp_word:
                                if y < margin + line_height:
                                    c.showPage()
                                    if grid_enabled:
                                        generate_grid_background(c, page_size, cell_size)
                                    y = get_initial_y()
                                
                                current_x = x
                                safe_draw_string(c, current_x, y, temp_word, font_name, font_size, font_path, font_names)
                                y -= line_height
                                first_line_in_paragraph = False
                                effective_max_width = max_width
                            temp_word = char
                    if temp_word:
                        if y < margin + line_height:
                            c.showPage()
                            if grid_enabled:
                                generate_grid_background(c, page_size, cell_size)
                            y = get_initial_y()
                        
                        current_x = x
                        safe_draw_string(c, current_x, y, temp_word, font_name, font_size, font_path, font_names)
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
                        
                        if y < margin + line_height:
                            c.showPage()
                            if grid_enabled:
                                generate_grid_background(c, page_size, cell_size)
                            y = get_initial_y()
                        
                        safe_draw_string(c, current_x, y, words_line, font_name, font_size, font_path, font_names)
                        y -= line_height
                        
                        first_line_in_paragraph = False
                        effective_max_width = max_width
                    
                    current_line = [word]
                    current_width = word_width
            
            # Рисуем последнюю строку абзаца
            if current_line:
                current_x = x
                words_line = ' '.join(current_line)
                
                if y < margin + line_height:
                    c.showPage()
                    if grid_enabled:
                        generate_grid_background(c, page_size, cell_size)
                    y = get_initial_y()
                
                safe_draw_string(c, current_x, y, words_line, font_name, font_size, font_path, font_names)
                y -= line_height
                first_line_in_paragraph = False
        
        # Отступ между абзацами
        y -= paragraph_spacing
        first_line_in_paragraph = True
    
    # Сохраняем PDF
    c.save()


def generate_pdf_for_job(job_id: int, text_content: str, font_path: str, page_format: str, grid_enabled: bool = False, variant_fonts: list = None) -> str:
    """
    Генерирует PDF для задачи из jobs таблицы
    
    Returns:
        Путь к созданному PDF файлу
    """
    # Проверка параметров
    if not job_id or job_id <= 0:
        raise ValueError("Некорректный ID задачи")
    
    if not text_content:
        raise ValueError("Текст не может быть пустым")
    
    if not font_path:
        raise ValueError("Путь к шрифту не указан")
    
    if not page_format:
        raise ValueError("Формат страницы не указан")
    
    os.makedirs(GENERATED_DIR, exist_ok=True)
    output_path = os.path.join(GENERATED_DIR, f"job_{job_id}.pdf")
    
    generate_pdf(text_content, font_path, page_format, output_path, grid_enabled, variant_fonts)
    
    return output_path

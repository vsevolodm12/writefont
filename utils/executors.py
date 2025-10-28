"""Thread pool для тяжелых синхронных операций"""
from concurrent.futures import ThreadPoolExecutor

# Пул из 4 потоков для генерации PDF
pdf_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="pdf_generator")


"""
Анализатор шрифтов: определение поддерживаемых наборов символов.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Set

from fontTools.ttLib import TTFont


CYRILLIC_LOWER = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
CYRILLIC_UPPER = CYRILLIC_LOWER.upper()
LATIN_LOWER = "abcdefghijklmnopqrstuvwxyz"
LATIN_UPPER = LATIN_LOWER.upper()
DIGITS = "0123456789"
COMMON_SYMBOLS = ".,:;!?\"'()[]{}@#$%^&*-+=/_\\|<>`~«»—–"


@dataclass
class FontCapabilities:
    path: str
    supports_cyrillic_lower: bool
    supports_cyrillic_upper: bool
    supports_latin_lower: bool
    supports_latin_upper: bool
    supports_digits: bool
    supports_symbols: bool
    coverage_score: int

    @property
    def is_cyrillic_full(self) -> bool:
        return self.supports_cyrillic_lower and self.supports_cyrillic_upper

    @property
    def has_any_letters(self) -> bool:
        return (
            self.supports_cyrillic_lower
            or self.supports_cyrillic_upper
            or self.supports_latin_lower
            or self.supports_latin_upper
        )

    @property
    def font_type(self) -> str:
        if self.is_cyrillic_full:
            return "cyrillic_full"
        if (
            self.supports_cyrillic_lower
            or self.supports_cyrillic_upper
        ):
            return "cyrillic_partial"
        if (
            (self.supports_latin_lower or self.supports_latin_upper)
            and not (self.supports_cyrillic_lower or self.supports_cyrillic_upper)
        ):
            return "latin"
        if self.supports_digits and not self.has_any_letters:
            return "digits"
        if self.has_any_letters:
            return "mixed"
        return "other"


def _collect_codepoints(tt_font: TTFont) -> Set[int]:
    codepoints: Set[int] = set()
    cmap = tt_font.get("cmap")
    if not cmap:
        return codepoints
    for table in cmap.tables:
        codepoints.update(table.cmap.keys())
    return codepoints


def _has_all(codepoints: Set[int], chars: Iterable[str]) -> bool:
    return all(ord(ch) in codepoints for ch in chars)


def analyze_font(font_path: str) -> FontCapabilities:
    """Возвращает информацию о поддерживаемых символах шрифта."""
    tt_font = TTFont(font_path)
    codepoints = _collect_codepoints(tt_font)
    tt_font.close()

    supports_cyrillic_lower = _has_all(codepoints, CYRILLIC_LOWER)
    supports_cyrillic_upper = _has_all(codepoints, CYRILLIC_UPPER)
    supports_latin_lower = _has_all(codepoints, LATIN_LOWER)
    supports_latin_upper = _has_all(codepoints, LATIN_UPPER)
    supports_digits = _has_all(codepoints, DIGITS)
    supports_symbols = _has_all(codepoints, COMMON_SYMBOLS)

    coverage_score = len(codepoints)

    return FontCapabilities(
        path=font_path,
        supports_cyrillic_lower=supports_cyrillic_lower,
        supports_cyrillic_upper=supports_cyrillic_upper,
        supports_latin_lower=supports_latin_lower,
        supports_latin_upper=supports_latin_upper,
        supports_digits=supports_digits,
        supports_symbols=supports_symbols,
        coverage_score=coverage_score,
    )


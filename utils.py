"""
Утилиты нормализации пользовательского ввода.
"""

import re
import unicodedata


def normalize_text(raw: str) -> str:
    """
    Приводит произвольный текст к нормальному виду:
    - убирает лишние пробелы / переносы
    - убирает управляющие символы
    - нормализует Unicode (NFC)
    """
    if not raw:
        return ""
    # Unicode NFC
    text = unicodedata.normalize("NFC", raw)
    # Убираем управляющие символы кроме пробела
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cc" or ch == " ")
    # Схлопываем пробелы
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_name(raw: str) -> str:
    """
    Нормализует имя языка:
    Title Case, убирает лишние символы кроме букв, пробелов и дефисов.
    """
    text = normalize_text(raw)
    # Оставляем только буквы, пробелы и дефис
    text = re.sub(r"[^\w\s\-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    # Title case
    return text.title() if text else ""


def normalize_word_pair(raw: str) -> tuple[str, str] | None:
    """
    Парсит строку вида "слово - перевод" или "слово: перевод".
    Возвращает (word, translation) или None если разобрать не удалось.
    Регистр: word → lowercase, translation → lowercase.
    """
    text = normalize_text(raw)
    if not text:
        return None

    # Пробуем разделители: " - ", " – ", " — ", ": ", " / "
    for sep in [" - ", " – ", " — ", ": ", " / ", "-", "–", "—", "/", ":"]:
        parts = text.split(sep, 1)
        if len(parts) == 2:
            word = normalize_text(parts[0]).lower()
            translation = normalize_text(parts[1]).lower()
            if word and translation:
                return word, translation

    return None


def validate_name(name: str) -> tuple[bool, str]:
    """Returns (valid, error_message)."""
    if not name:
        return False, "Имя не может быть пустым."
    if len(name) > 50:
        return False, "Имя слишком длинное (максимум 50 символов)."
    return True, ""

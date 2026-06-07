"""
Фабрика клавиатур Telegram.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    """Shorthand: kb([[("label","data"), ...], ...])"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=data) for label, data in row]
        for row in rows
    ])


def main_menu_kb() -> InlineKeyboardMarkup:
    return kb([
        [("🌍 Мои языки", "languages")],
        [("📚 Мои слова", "my_words")],
        [("ℹ️ Помощь", "help")],
    ])


def languages_list_kb(langs) -> InlineKeyboardMarkup:
    rows = []
    for lang in langs:
        rows.append([
            (f"📖 {lang['name']}", f"lang_open:{lang['id']}"),
        ])
    rows.append([("➕ Добавить язык", "lang_add")])
    rows.append([("🏠 Главное меню", "menu")])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=data) for label, data in row]
        for row in rows
    ])


def language_menu_kb(lang_id: int) -> InlineKeyboardMarkup:
    return kb([
        [("📝 Слова", f"word_list:{lang_id}"),
         ("➕ Добавить слово", f"word_add:{lang_id}")],
        [("✏️ Переименовать язык", f"lang_rename:{lang_id}"),
         ("🗑 Удалить язык", f"lang_delete:{lang_id}")],
        [("🌍 Все языки", "languages")],
        [("🏠 Главное меню", "menu")],
    ])


def word_list_kb(words, lang_id: int, page: int = 0, page_size: int = 8) -> InlineKeyboardMarkup:
    total = len(words)
    start = page * page_size
    end = min(start + page_size, total)
    rows = []
    for w in words[start:end]:
        rows.append([
            (f"{w['word']} — {w['translation']}", f"word_open:{w['id']}"),
        ])
    # Пагинация
    nav = []
    if page > 0:
        nav.append(("◀️", f"word_page:{lang_id}:{page-1}"))
    if end < total:
        nav.append(("▶️", f"word_page:{lang_id}:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([("➕ Добавить слово", f"word_add:{lang_id}")])
    rows.append([("🔙 К языку", f"lang_open:{lang_id}"),
                 ("🏠 Меню", "menu")])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=data) for label, data in row]
        for row in rows
    ])


def word_menu_kb(word_id: int, lang_id: int) -> InlineKeyboardMarkup:
    return kb([
        [("✏️ Редактировать", f"word_edit:{word_id}"),
         ("🗑 Удалить", f"word_delete:{word_id}")],
        [("🔀 Переместить в другой язык", f"word_move:{word_id}")],
        [("🔙 К словам", f"word_list:{lang_id}"),
         ("🏠 Меню", "menu")],
    ])


def move_lang_kb(langs, word_id: int, current_lang_id: int) -> InlineKeyboardMarkup:
    rows = []
    for lang in langs:
        if lang["id"] != current_lang_id:
            rows.append([
                (f"📖 {lang['name']}", f"word_move_to:{word_id}:{lang['id']}"),
            ])
    rows.append([("❌ Отмена", f"word_open:{word_id}")])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=data) for label, data in row]
        for row in rows
    ])


def confirm_delete_lang_kb(lang_id: int) -> InlineKeyboardMarkup:
    return kb([
        [("✅ Да, удалить язык и все слова", f"lang_delete_confirm:{lang_id}")],
        [("❌ Отмена", f"lang_open:{lang_id}")],
    ])


def cancel_kb(back_data: str = "menu") -> InlineKeyboardMarkup:
    return kb([[("❌ Отмена", back_data)]])


def review_kb(word_id: int) -> InlineKeyboardMarkup:
    return kb([
        [("✅ Знаю!", f"review:ok:{word_id}"),
         ("❌ Не вспомнил", f"review:fail:{word_id}")],
    ])

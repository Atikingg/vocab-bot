"""
Обработчики для управления языками.
"""

import asyncio
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CallbackQueryHandler, MessageHandler, filters
)
import database as db
from keyboards import (
    languages_list_kb, language_menu_kb, confirm_delete_lang_kb, cancel_kb
)
from utils import normalize_name, validate_name

# Состояния ConversationHandler
LANG_ADD_NAME   = "LANG_ADD_NAME"
LANG_RENAME     = "LANG_RENAME"


def _uid(update: Update) -> int:
    if update.callback_query:
        return update.callback_query.from_user.id
    return update.effective_user.id


async def _run(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


# ─── List ──────────────────────────────────────────────────────────────────────

async def show_languages(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    langs = await _run(db.get_languages, _uid(update))
    if not langs:
        text = "🌍 *Языки*\n\nУ вас пока нет добавленных языков.\nДобавьте первый язык!"
    else:
        text = f"🌍 *Языки* ({len(langs)})\n\nВыберите язык или добавьте новый:"
    await q.edit_message_text(
        text, parse_mode="Markdown", reply_markup=languages_list_kb(langs)
    )
    return ConversationHandler.END


# ─── Add ───────────────────────────────────────────────────────────────────────

async def lang_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🌍 *Добавление языка*\n\nВведите название языка (например: *Английский*):",
        parse_mode="Markdown",
        reply_markup=cancel_kb("languages")
    )
    return LANG_ADD_NAME


async def lang_add_receive(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text or ""
    name = normalize_name(raw)
    valid, err = validate_name(name)
    if not valid:
        await update.message.reply_text(
            f"⚠️ {err}\nПопробуйте ещё раз:",
            reply_markup=cancel_kb("languages")
        )
        return LANG_ADD_NAME

    ok, reason = await _run(db.add_language, _uid(update), name)
    if not ok and reason == "exists":
        await update.message.reply_text(
            f"⚠️ Язык *{name}* уже существует. Введите другое название:",
            parse_mode="Markdown",
            reply_markup=cancel_kb("languages")
        )
        return LANG_ADD_NAME

    langs = await _run(db.get_languages, _uid(update))
    await update.message.reply_text(
        f"✅ Язык *{name}* добавлен!\n\nВыберите язык:",
        parse_mode="Markdown",
        reply_markup=languages_list_kb(langs)
    )
    return ConversationHandler.END


# ─── Open ──────────────────────────────────────────────────────────────────────

async def lang_open(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang_id = int(q.data.split(":")[1])
    ctx.user_data["current_lang_id"] = lang_id
    lang = await _run(db.get_language, lang_id, _uid(update))
    if not lang:
        await q.edit_message_text("⚠️ Язык не найден.", reply_markup=cancel_kb("languages"))
        return ConversationHandler.END
    count = await _run(db.count_words_in_language, lang_id, _uid(update))
    await q.edit_message_text(
        f"📖 *{lang['name']}*\nСлов: {count}",
        parse_mode="Markdown",
        reply_markup=language_menu_kb(lang_id)
    )
    return ConversationHandler.END


# ─── Rename ────────────────────────────────────────────────────────────────────

async def lang_rename_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang_id = int(q.data.split(":")[1])
    ctx.user_data["rename_lang_id"] = lang_id
    lang = await _run(db.get_language, lang_id, _uid(update))
    if not lang:
        await q.edit_message_text("⚠️ Язык не найден.")
        return ConversationHandler.END
    await q.edit_message_text(
        f"✏️ *Переименование языка*\n\nТекущее название: *{lang['name']}*\n\nВведите новое название:",
        parse_mode="Markdown",
        reply_markup=cancel_kb(f"lang_open:{lang_id}")
    )
    return LANG_RENAME


async def lang_rename_receive(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text or ""
    name = normalize_name(raw)
    valid, err = validate_name(name)
    lang_id = ctx.user_data.get("rename_lang_id")
    if not lang_id:
        await update.message.reply_text("⚠️ Сессия истекла. Начните заново.", reply_markup=cancel_kb())
        return ConversationHandler.END

    if not valid:
        await update.message.reply_text(
            f"⚠️ {err}\nПопробуйте ещё раз:",
            reply_markup=cancel_kb(f"lang_open:{lang_id}")
        )
        return LANG_RENAME

    ok, reason = await _run(db.rename_language, lang_id, _uid(update), name)
    if not ok:
        msg = "⚠️ Язык с таким именем уже существует." if reason == "exists" else "⚠️ Язык не найден."
        await update.message.reply_text(
            f"{msg}\nПопробуйте ещё раз:",
            reply_markup=cancel_kb(f"lang_open:{lang_id}")
        )
        return LANG_RENAME

    lang = await _run(db.get_language, lang_id, _uid(update))
    count = await _run(db.count_words_in_language, lang_id, _uid(update))
    await update.message.reply_text(
        f"✅ Язык переименован в *{name}*!",
        parse_mode="Markdown",
        reply_markup=language_menu_kb(lang_id)
    )
    return ConversationHandler.END


# ─── Delete ────────────────────────────────────────────────────────────────────

async def lang_delete_ask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang_id = int(q.data.split(":")[1])
    lang = await _run(db.get_language, lang_id, _uid(update))
    if not lang:
        await q.edit_message_text("⚠️ Язык не найден.")
        return ConversationHandler.END
    count = await _run(db.count_words_in_language, lang_id, _uid(update))
    await q.edit_message_text(
        f"⚠️ *Удаление языка*\n\n"
        f"Вы собираетесь удалить язык *{lang['name']}* и все его слова ({count} шт.).\n\n"
        f"Это действие *необратимо*. Вы уверены?",
        parse_mode="Markdown",
        reply_markup=confirm_delete_lang_kb(lang_id)
    )
    return ConversationHandler.END


async def lang_delete_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang_id = int(q.data.split(":")[1])
    lang = await _run(db.get_language, lang_id, _uid(update))
    name = lang["name"] if lang else "?"
    await _run(db.delete_language, lang_id, _uid(update))
    langs = await _run(db.get_languages, _uid(update))
    await q.edit_message_text(
        f"🗑 Язык *{name}* и все его слова удалены.",
        parse_mode="Markdown",
        reply_markup=languages_list_kb(langs)
    )
    return ConversationHandler.END


# ─── My words (cross-language) ────────────────────────────────────────────────

async def my_words_overview(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    langs = await _run(db.get_languages, _uid(update))
    if not langs:
        from keyboards import main_menu_kb
        await q.edit_message_text(
            "📚 У вас пока нет языков.\nДобавьте язык сначала!",
            reply_markup=main_menu_kb()
        )
        return ConversationHandler.END
    # Показываем языки со счётчиком
    from keyboards import kb
    rows = []
    for lang in langs:
        count = await _run(db.count_words_in_language, lang["id"], _uid(update))
        rows.append([(f"📖 {lang['name']} ({count} сл.)", f"word_list:{lang['id']}:{0}")])
    rows.append([("🏠 Главное меню", "menu")])
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=data) for label, data in row]
        for row in rows
    ])
    await q.edit_message_text(
        "📚 *Мои слова*\n\nВыберите язык:",
        parse_mode="Markdown",
        reply_markup=markup
    )
    return ConversationHandler.END


# ─── Help ──────────────────────────────────────────────────────────────────────

async def show_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    from keyboards import main_menu_kb
    text = (
        "ℹ️ *Помощь*\n\n"
        "🔸 *Языки* — добавляйте языки, которые изучаете.\n"
        "🔸 *Слова* — добавляйте слова в формате:\n"
        "   `слово — перевод`\n"
        "   (разделитель: дефис, двоеточие или слеш)\n\n"
        "🔸 *Повторения* — бот сам напомнит, когда пора повторить слово:\n"
        "   20 мин → 1 ч → 8 ч → 1 д → 3 д → 7 д → 14 д → 30 д\n\n"
        "🔸 Если знаете слово — нажмите ✅, не вспомнили — ❌ (начнёт сначала).\n\n"
        "🔸 Слова можно редактировать и перемещать между языками."
    )
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu_kb())
    return ConversationHandler.END


# ─── States map ───────────────────────────────────────────────────────────────

STATES = {
    LANG_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, lang_add_receive)],
    LANG_RENAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, lang_rename_receive)],
}

# Регистрируем CallbackQuery handlers (вызываются из ConversationHandler entry/state)
CALLBACK_HANDLERS = [
    CallbackQueryHandler(show_languages,      pattern="^languages$"),
    CallbackQueryHandler(lang_add_start,      pattern="^lang_add$"),
    CallbackQueryHandler(lang_open,           pattern="^lang_open:"),
    CallbackQueryHandler(lang_rename_start,   pattern="^lang_rename:"),
    CallbackQueryHandler(lang_delete_ask,     pattern="^lang_delete:"),
    CallbackQueryHandler(lang_delete_confirm, pattern="^lang_delete_confirm:"),
    CallbackQueryHandler(my_words_overview,   pattern="^my_words$"),
    CallbackQueryHandler(show_help,           pattern="^help$"),
]

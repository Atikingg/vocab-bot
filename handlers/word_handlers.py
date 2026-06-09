"""
Обработчики для управления словами.
"""

import asyncio
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CallbackQueryHandler, MessageHandler, filters
)
import database as db
from keyboards import (
    word_list_kb, word_menu_kb, move_lang_kb, cancel_kb
)
from utils import normalize_word_pair, normalize_text, validate_name

WORD_ADD    = "WORD_ADD"
WORD_EDIT   = "WORD_EDIT"


def _uid(update: Update) -> int:
    if update.callback_query:
        return update.callback_query.from_user.id
    return update.effective_user.id


async def _run(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


# ─── List ──────────────────────────────────────────────────────────────────────

async def word_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    lang_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0
    lang = await _run(db.get_language, lang_id, _uid(update))
    if not lang:
        await q.edit_message_text("⚠️ Язык не найден.")
        return ConversationHandler.END
    words = await _run(db.get_words, _uid(update), lang_id)
    if not words:
        await q.edit_message_text(
            f"📚 *{lang['name']}* — слов нет.\n\nДобавьте первое слово!",
            parse_mode="Markdown",
            reply_markup=word_list_kb([], lang_id)
        )
        return ConversationHandler.END
    await q.edit_message_text(
        f"📚 *{lang['name']}* — {len(words)} сл.",
        parse_mode="Markdown",
        reply_markup=word_list_kb(words, lang_id, page)
    )
    return ConversationHandler.END


async def word_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    lang_id = int(parts[1])
    page = int(parts[2])
    lang = await _run(db.get_language, lang_id, _uid(update))
    if not lang:
        await q.edit_message_text("⚠️ Язык не найден.")
        return ConversationHandler.END
    words = await _run(db.get_words, _uid(update), lang_id)
    await q.edit_message_text(
        f"📚 *{lang['name']}* — {len(words)} сл.",
        parse_mode="Markdown",
        reply_markup=word_list_kb(words, lang_id, page)
    )
    return ConversationHandler.END


# ─── Open ──────────────────────────────────────────────────────────────────────

async def word_open(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    word_id = int(q.data.split(":")[1])
    word = await _run(db.get_word, word_id, _uid(update))
    if not word:
        await q.edit_message_text("⚠️ Слово не найдено.", reply_markup=cancel_kb("menu"))
        return ConversationHandler.END

    from config import EBBINGHAUS_INTERVALS_MINUTES
    step = word["interval_step"]
    total = len(EBBINGHAUS_INTERVALS_MINUTES)
    if word["next_review"] == "":
        progress = "✅ Выучено!"
    else:
        progress = f"Шаг {step}/{total}"

    text = (
        f"📝 *{word['word']}* — {word['translation']}\n"
        f"🌍 Язык: {word['lang_name']}\n"
        f"📅 Добавлено: {word['added_at'][:10]}\n"
        f"🔄 Прогресс: {progress}"
    )
    await q.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=word_menu_kb(word_id, word["lang_id"])
    )
    return ConversationHandler.END


# ─── Add ───────────────────────────────────────────────────────────────────────

async def word_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang_id = int(q.data.split(":")[1])
    ctx.user_data["add_word_lang_id"] = lang_id
    lang = await _run(db.get_language, lang_id, _uid(update))
    if not lang:
        await q.edit_message_text("⚠️ Язык не найден.")
        return ConversationHandler.END
    await q.edit_message_text(
        f"➕ *Добавление слов* в «{lang['name']}»\n\n"
        "Введите одно слово или сразу список — каждое с новой строки:\n\n"
        "`hello — привет`\n"
        "`cat — кот`\n"
        "`dog — собака`\n\n"
        "Разделитель: дефис, двоеточие или слеш.",
        parse_mode="Markdown",
        reply_markup=cancel_kb(f"lang_open:{lang_id}")
    )
    return WORD_ADD


async def word_add_receive(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text or ""
    lang_id = ctx.user_data.get("add_word_lang_id")
    if not lang_id:
        await update.message.reply_text("⚠️ Сессия истекла. Начните заново.", reply_markup=cancel_kb())
        return ConversationHandler.END

    # Разбиваем на строки и парсим каждую
    lines = [l.strip() for l in raw.splitlines() if l.strip()]

    added = []
    duplicates = []
    failed = []

    for line in lines:
        pair = normalize_word_pair(line)
        if not pair:
            # Пробуем игнорировать строку если она совсем не похожа на пару
            if len(line) > 1:
                failed.append(line)
            continue
        word, translation = pair
        ok, reason = await _run(db.add_word, _uid(update), lang_id, word, translation)
        if ok:
            added.append(f"{word} — {translation}")
        elif reason == "exists":
            duplicates.append(word)

    # Формируем ответ
    parts = []

    if added:
        if len(added) == 1:
            parts.append(f"✅ Добавлено: *{added[0]}*\n\nПервое повторение через 20 минут. 🕐")
        else:
            words_list = "\n".join(f"• {w}" for w in added)
            parts.append(f"✅ Добавлено {len(added)} слов:\n{words_list}\n\nПервое повторение через 20 минут. 🕐")

    if duplicates:
        dup_list = ", ".join(f"*{w}*" for w in duplicates)
        parts.append(f"⚠️ Уже существуют: {dup_list}")

    if failed:
        fail_list = "\n".join(f"• {l}" for l in failed[:5])  # не более 5
        parts.append(f"❓ Не удалось распознать:\n{fail_list}\nФормат: `слово — перевод`")

    if not added and not duplicates and not failed:
        await update.message.reply_text(
            "⚠️ Не удалось распознать ни одного слова.\n\n"
            "Введите в формате:\n`слово — перевод`",
            parse_mode="Markdown",
            reply_markup=cancel_kb(f"lang_open:{lang_id}")
        )
        return WORD_ADD

    if not added and not duplicates:
        await update.message.reply_text(
            "\n\n".join(parts),
            parse_mode="Markdown",
            reply_markup=cancel_kb(f"lang_open:{lang_id}")
        )
        return WORD_ADD

    words = await _run(db.get_words, _uid(update), lang_id)
    await update.message.reply_text(
        "\n\n".join(parts),
        parse_mode="Markdown",
        reply_markup=word_list_kb(words, lang_id)
    )
    return ConversationHandler.END


# ─── Edit ──────────────────────────────────────────────────────────────────────

async def word_edit_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    word_id = int(q.data.split(":")[1])
    word = await _run(db.get_word, word_id, _uid(update))
    if not word:
        await q.edit_message_text("⚠️ Слово не найдено.")
        return ConversationHandler.END
    ctx.user_data["edit_word_id"] = word_id
    ctx.user_data["edit_word_lang_id"] = word["lang_id"]
    await q.edit_message_text(
        f"✏️ *Редактирование*\n\n"
        f"Текущее: *{word['word']}* — {word['translation']}\n\n"
        "Введите новое значение:\n`слово — перевод`",
        parse_mode="Markdown",
        reply_markup=cancel_kb(f"word_open:{word_id}")
    )
    return WORD_EDIT


async def word_edit_receive(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text or ""
    word_id = ctx.user_data.get("edit_word_id")
    lang_id = ctx.user_data.get("edit_word_lang_id")
    if not word_id:
        await update.message.reply_text("⚠️ Сессия истекла.", reply_markup=cancel_kb())
        return ConversationHandler.END

    pair = normalize_word_pair(raw)
    if not pair:
        await update.message.reply_text(
            "⚠️ Не удалось распознать формат.\n`слово — перевод`",
            parse_mode="Markdown",
            reply_markup=cancel_kb(f"word_open:{word_id}")
        )
        return WORD_EDIT

    word, translation = pair
    ok = await _run(db.update_word, word_id, _uid(update), word, translation)
    if not ok:
        await update.message.reply_text(
            "⚠️ Такое слово уже существует в этом языке.\nВведите другое:",
            reply_markup=cancel_kb(f"word_open:{word_id}")
        )
        return WORD_EDIT

    words = await _run(db.get_words, _uid(update), lang_id)
    await update.message.reply_text(
        f"✅ Слово обновлено: *{word}* — {translation}",
        parse_mode="Markdown",
        reply_markup=word_list_kb(words, lang_id)
    )
    return ConversationHandler.END


# ─── Delete ────────────────────────────────────────────────────────────────────

async def word_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    word_id = int(q.data.split(":")[1])
    word = await _run(db.get_word, word_id, _uid(update))
    if not word:
        await q.edit_message_text("⚠️ Слово не найдено.")
        return ConversationHandler.END
    lang_id = word["lang_id"]
    label = f"{word['word']} — {word['translation']}"
    await _run(db.delete_word, word_id, _uid(update))
    words = await _run(db.get_words, _uid(update), lang_id)
    await q.edit_message_text(
        f"🗑 Слово *{label}* удалено.",
        parse_mode="Markdown",
        reply_markup=word_list_kb(words, lang_id)
    )
    return ConversationHandler.END


# ─── Move ──────────────────────────────────────────────────────────────────────

async def word_move_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    word_id = int(q.data.split(":")[1])
    word = await _run(db.get_word, word_id, _uid(update))
    if not word:
        await q.edit_message_text("⚠️ Слово не найдено.")
        return ConversationHandler.END
    langs = await _run(db.get_languages, _uid(update))
    other_langs = [l for l in langs if l["id"] != word["lang_id"]]
    if not other_langs:
        await q.edit_message_text(
            "⚠️ Нет других языков для перемещения.\nСначала добавьте ещё один язык.",
            reply_markup=cancel_kb(f"word_open:{word_id}")
        )
        return ConversationHandler.END
    await q.edit_message_text(
        f"🔀 *Перемещение слова*\n\n"
        f"*{word['word']}* — {word['translation']}\n\n"
        "Выберите язык назначения:",
        parse_mode="Markdown",
        reply_markup=move_lang_kb(langs, word_id, word["lang_id"])
    )
    return ConversationHandler.END


async def word_move_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, word_id_s, new_lang_id_s = q.data.split(":")
    word_id = int(word_id_s)
    new_lang_id = int(new_lang_id_s)
    ok, reason = await _run(db.move_word, word_id, _uid(update), new_lang_id)
    if not ok:
        msg = "⚠️ Такое слово уже существует в целевом языке." if reason == "exists" else "⚠️ Слово не найдено."
        await q.edit_message_text(msg, reply_markup=cancel_kb(f"word_open:{word_id}"))
        return ConversationHandler.END
    lang = await _run(db.get_language, new_lang_id, _uid(update))
    words = await _run(db.get_words, _uid(update), new_lang_id)
    await q.edit_message_text(
        f"✅ Слово перемещено в *{lang['name']}*.\nПрогресс повторений сброшен.",
        parse_mode="Markdown",
        reply_markup=word_list_kb(words, new_lang_id)
    )
    return ConversationHandler.END


# ─── States map ───────────────────────────────────────────────────────────────

STATES = {
    WORD_ADD:  [MessageHandler(filters.TEXT & ~filters.COMMAND, word_add_receive)],
    WORD_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, word_edit_receive)],
}

CALLBACK_HANDLERS = [
    CallbackQueryHandler(word_list,          pattern="^word_list:"),
    CallbackQueryHandler(word_page,          pattern="^word_page:"),
    CallbackQueryHandler(word_open,          pattern="^word_open:"),
    CallbackQueryHandler(word_add_start,     pattern="^word_add:"),
    CallbackQueryHandler(word_edit_start,    pattern="^word_edit:"),
    CallbackQueryHandler(word_delete,        pattern="^word_delete:"),
    CallbackQueryHandler(word_move_start,    pattern="^word_move:[0-9]+$"),
    CallbackQueryHandler(word_move_confirm,  pattern="^word_move_to:"),
]

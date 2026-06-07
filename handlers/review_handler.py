"""
Обработчик кнопок в уведомлениях о повторении.
"""

import asyncio
from telegram import Update
from telegram.ext import ContextTypes
import database as db
from keyboards import review_kb, main_menu_kb


def _uid(update: Update) -> int:
    return update.callback_query.from_user.id


async def _run(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


async def handle_review(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")  # review:ok:word_id or review:fail:word_id
    action  = parts[1]
    word_id = int(parts[2])

    word = await _run(db.get_word, word_id, _uid(update))
    if not word:
        await q.edit_message_text("⚠️ Слово уже удалено.")
        return

    if action == "ok":
        await _run(db.advance_word, word_id)
        # Проверяем, не выучено ли
        updated = await _run(db.get_word, word_id, _uid(update))
        if updated and updated["next_review"] == "":
            await q.edit_message_text(
                f"🏆 *{word['word']}* выучено! Поздравляем!\n\n"
                "Оно больше не появится в повторениях.",
                parse_mode="Markdown",
                reply_markup=main_menu_kb()
            )
        else:
            from config import EBBINGHAUS_INTERVALS_MINUTES
            if updated:
                step = updated["interval_step"]
                intervals = EBBINGHAUS_INTERVALS_MINUTES
                if step < len(intervals):
                    mins = intervals[step]
                    if mins < 60:
                        when = f"{mins} мин."
                    elif mins < 1440:
                        when = f"{mins // 60} ч."
                    else:
                        when = f"{mins // 1440} д."
                    next_info = f"Следующее повторение через {when}"
                else:
                    next_info = "Скоро выучите!"
            else:
                next_info = ""
            await q.edit_message_text(
                f"✅ Отлично! *{word['word']}* — {word['translation']}\n\n{next_info}",
                parse_mode="Markdown",
                reply_markup=main_menu_kb()
            )
    else:  # fail
        await _run(db.reset_word, word_id)
        await q.edit_message_text(
            f"🔄 Не страшно! *{word['word']}* — {word['translation']}\n\n"
            "Прогресс сброшен. Повторим через 20 минут.",
            parse_mode="Markdown",
            reply_markup=main_menu_kb()
        )


async def handle_snooze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Напомним позже!")
    await q.edit_message_text(
        "⏰ Хорошо, напомним позже.",
        reply_markup=main_menu_kb()
    )

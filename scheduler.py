"""
Планировщик уведомлений по кривой Эббингауза.
Каждую минуту проверяет БД и отправляет уведомления.
"""

import asyncio
import logging
from datetime import datetime, timezone
from telegram.ext import Application
from telegram.error import TelegramError
import database as db
from keyboards import review_kb

logger = logging.getLogger(__name__)

# word_id → True, чтобы не слать дубли пока пользователь не ответил
_sent: set[int] = set()


async def _check_and_send(app: Application):
    try:
        loop = asyncio.get_event_loop()
        due = await loop.run_in_executor(None, db.get_due_words)
    except Exception as e:
        logger.error(f"Scheduler DB error: {e}")
        return

    for word in due:
        word_id = word["id"]
        if word_id in _sent:
            continue
        if not word["next_review"]:  # выучено
            continue
        user_id = word["user_id"]
        text = (
            f"🔔 *Пора повторить слово!*\n\n"
            f"*{word['word']}* — ?\n"
            f"Язык: {word['lang_name']}"
        )
        try:
            await app.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=review_kb(word_id)
            )
            _sent.add(word_id)
            logger.info(f"Sent review for word {word_id} to user {user_id}")
        except TelegramError as e:
            logger.warning(f"Failed to send review to {user_id}: {e}")


def _cleanup_sent_cache():
    """Периодически чистим кэш отправленных уведомлений."""
    global _sent
    if len(_sent) > 10000:
        _sent = set()


async def _scheduler_loop(app: Application):
    while True:
        await _check_and_send(app)
        _cleanup_sent_cache()
        await asyncio.sleep(60)  # проверяем каждую минуту


def remove_from_sent(word_id: int):
    """Вызывается после ответа пользователя — слово снова может быть отправлено."""
    _sent.discard(word_id)


def start_scheduler(app: Application):
    async def _start(_app):
        asyncio.create_task(_scheduler_loop(_app))

    app.post_init = _start
    app.post_shutdown = None

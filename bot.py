#!/usr/bin/env python3
"""
Vocabulary Bot — учи слова по кривой Эббингауза.
"""

import logging
import asyncio
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters
)
from config import BOT_TOKEN
from handlers import start_handler, main_menu_handler
from handlers import language_handlers as lh
from handlers import word_handlers as wh
from handlers import review_handler
from scheduler import start_scheduler

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Все callback entry points (кнопки)
    all_cb_entries = [
        CallbackQueryHandler(main_menu_handler.handle,          pattern="^menu$"),
        # языки
        CallbackQueryHandler(lh.show_languages,                 pattern="^languages$"),
        CallbackQueryHandler(lh.lang_add_start,                 pattern="^lang_add$"),
        CallbackQueryHandler(lh.lang_open,                      pattern="^lang_open:"),
        CallbackQueryHandler(lh.lang_rename_start,              pattern="^lang_rename:"),
        CallbackQueryHandler(lh.lang_delete_ask,                pattern="^lang_delete:[0-9]+$"),
        CallbackQueryHandler(lh.lang_delete_confirm,            pattern="^lang_delete_confirm:"),
        CallbackQueryHandler(lh.my_words_overview,              pattern="^my_words$"),
        CallbackQueryHandler(lh.show_help,                      pattern="^help$"),
        # слова
        CallbackQueryHandler(wh.word_list,                      pattern="^word_list:"),
        CallbackQueryHandler(wh.word_page,                      pattern="^word_page:"),
        CallbackQueryHandler(wh.word_open,                      pattern="^word_open:"),
        CallbackQueryHandler(wh.word_add_start,                 pattern="^word_add:"),
        CallbackQueryHandler(wh.word_edit_start,                pattern="^word_edit:"),
        CallbackQueryHandler(wh.word_delete,                    pattern="^word_delete:"),
        CallbackQueryHandler(wh.word_move_start,                pattern="^word_move:[0-9]+$"),
        CallbackQueryHandler(wh.word_move_confirm,              pattern="^word_move_to:"),
    ]

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_handler.cmd_start),
            *all_cb_entries,
        ],
        states={
            lh.LANG_ADD_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lh.lang_add_receive),
                *all_cb_entries,
            ],
            lh.LANG_RENAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lh.lang_rename_receive),
                *all_cb_entries,
            ],
            wh.WORD_ADD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wh.word_add_receive),
                *all_cb_entries,
            ],
            wh.WORD_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wh.word_edit_receive),
                *all_cb_entries,
            ],
        },
        fallbacks=[
            CommandHandler("start", start_handler.cmd_start),
            CallbackQueryHandler(main_menu_handler.handle, pattern="^menu$"),
        ],
        allow_reentry=True,
        name="main_conv",
        persistent=False,
    )

    app.add_handler(conv_handler)

    # Уведомления — вне ConversationHandler
    app.add_handler(CallbackQueryHandler(review_handler.handle_review, pattern="^review:"))
    app.add_handler(CallbackQueryHandler(review_handler.handle_snooze, pattern="^snooze:"))

    # Запуск планировщика
    start_scheduler(app)

    logger.info("Vocab Bot started.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

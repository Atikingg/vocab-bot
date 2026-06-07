from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from keyboards import main_menu_kb

WELCOME = (
    "👋 Привет! Я *Vocab Bot* — помогу выучить слова на любом языке.\n\n"
    "📌 *Что я умею:*\n"
    "• Хранить слова и переводы по языкам\n"
    "• Напоминать об их повторении по *кривой Эббингауза*\n"
    "  (20 мин → 1 ч → 8 ч → 1 д → 3 д → 7 д → 14 д → 30 д)\n"
    "• Отслеживать ваш прогресс\n\n"
    "Всё управление — через кнопки. Начнём? 👇"
)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            WELCOME, parse_mode="Markdown", reply_markup=main_menu_kb()
        )
    else:
        q = update.callback_query
        await q.answer()
        await q.edit_message_text(
            WELCOME, parse_mode="Markdown", reply_markup=main_menu_kb()
        )
    return ConversationHandler.END

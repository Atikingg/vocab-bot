from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from keyboards import main_menu_kb


async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🏠 *Главное меню*\nВыберите действие:",
        parse_mode="Markdown",
        reply_markup=main_menu_kb()
    )
    return ConversationHandler.END

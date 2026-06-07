import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "8701178944:AAEXl-hw4D5vtQQ0C9Au4p88dJElw_mmQK0")
DB_PATH = os.getenv("DB_PATH", "vocab_bot.db")

# Кривая Эббингауза: интервалы повторений в минутах
# 20 мин → 1 ч → 8 ч → 1 д → 3 д → 7 д → 14 д → 30 д
EBBINGHAUS_INTERVALS_MINUTES = [20, 60, 480, 1440, 4320, 10080, 20160, 43200]

# 🧠 Vocab Bot — учи слова по кривой Эббингауза

Telegram-бот для запоминания иностранных слов с интервальными повторениями по кривой Эббингауза.

---

## ⚙️ Установка и запуск

### 1. Получите токен бота

1. Откройте Telegram, найдите [@BotFather](https://t.me/BotFather)
2. Отправьте `/newbot` и следуйте инструкциям
3. Скопируйте полученный токен

### 2. Установите зависимости

```bash
pip install -r requirements.txt
```

### 3. Задайте токен

**Вариант А — переменная окружения (рекомендуется):**
```bash
export BOT_TOKEN="ваш_токен_здесь"
python bot.py
```

**Вариант Б — напрямую в `config.py`:**
```python
BOT_TOKEN = "ваш_токен_здесь"
```

### 4. Запустите бота

```bash
python bot.py
```

---

## 📁 Структура файлов

```
vocab_bot/
├── bot.py              # Точка входа, регистрация хендлеров
├── config.py           # Токен, путь к БД, интервалы Эббингауза
├── database.py         # SQLite: языки, слова, прогресс
├── keyboards.py        # Все Inline-клавиатуры
├── scheduler.py        # Фоновый цикл уведомлений (каждые 60 сек)
├── utils.py            # Нормализация ввода
├── requirements.txt
└── handlers/
    ├── start_handler.py       # /start, приветствие
    ├── main_menu_handler.py   # Главное меню
    ├── language_handlers.py   # CRUD языков
    ├── word_handlers.py       # CRUD слов
    └── review_handler.py      # Кнопки в уведомлениях
```

---

## 📊 Кривая Эббингауза

Интервалы повторений для каждого слова:

| Шаг | Через       |
|-----|-------------|
| 1   | 20 минут    |
| 2   | 1 час       |
| 3   | 8 часов     |
| 4   | 1 день      |
| 5   | 3 дня       |
| 6   | 7 дней      |
| 7   | 14 дней     |
| 8   | 30 дней     |

После 8-го успешного повторения слово считается **выученным**.

Если нажать ❌ («Не вспомнил») — прогресс сбрасывается на начало.

---

## 🖥️ Для запуска 24/7 (Linux/systemd)

Создайте файл `/etc/systemd/system/vocabbot.service`:

```ini
[Unit]
Description=Vocab Telegram Bot
After=network.target

[Service]
User=your_user
WorkingDirectory=/path/to/vocab_bot
Environment=BOT_TOKEN=your_token_here
ExecStart=/usr/bin/python3 /path/to/vocab_bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable vocabbot
sudo systemctl start vocabbot
sudo systemctl status vocabbot
```

---

## 🐳 Docker (опционально)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV BOT_TOKEN=""
ENV DB_PATH="/data/vocab_bot.db"
VOLUME ["/data"]
CMD ["python", "bot.py"]
```

```bash
docker build -t vocabbot .
docker run -d \
  -e BOT_TOKEN="ваш_токен" \
  -v vocabbot_data:/data \
  --name vocabbot \
  vocabbot
```

---

## 💡 Особенности

- **Все данные каждого пользователя хранятся отдельно** (по user_id)
- **Нормализация ввода**: регистр, лишние пробелы, разные разделители (`-`, `—`, `:`, `/`)
- **Пагинация** при большом количестве слов (8 слов на страницу)
- **Подтверждение** при удалении языка (с предупреждением о потере всех слов)
- **Без команд** — всё управление через inline-кнопки

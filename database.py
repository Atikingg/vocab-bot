"""
Слой работы с SQLite.
Все операции — синхронные, вызываются из asyncio через run_in_executor.
"""

import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional
from config import DB_PATH, EBBINGHAUS_INTERVALS_MINUTES

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_db():
    conn = _get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS languages (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name    TEXT    NOT NULL,
        UNIQUE(user_id, name)
    );

    CREATE TABLE IF NOT EXISTS words (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        lang_id     INTEGER NOT NULL REFERENCES languages(id) ON DELETE CASCADE,
        word        TEXT    NOT NULL,
        translation TEXT    NOT NULL,
        added_at    TEXT    NOT NULL,
        next_review TEXT    NOT NULL,
        interval_step INTEGER NOT NULL DEFAULT 0,
        UNIQUE(user_id, lang_id, word)
    );

    CREATE INDEX IF NOT EXISTS idx_words_review ON words(user_id, next_review);
    CREATE INDEX IF NOT EXISTS idx_words_lang   ON words(user_id, lang_id);
    """)
    conn.commit()


# ─── Languages ────────────────────────────────────────────────────────────────

def add_language(user_id: int, name: str) -> tuple[bool, str]:
    """Returns (ok, message)."""
    try:
        _get_conn().execute(
            "INSERT INTO languages(user_id, name) VALUES (?,?)", (user_id, name)
        )
        _get_conn().commit()
        return True, "ok"
    except sqlite3.IntegrityError:
        return False, "exists"


def get_languages(user_id: int) -> list[sqlite3.Row]:
    return _get_conn().execute(
        "SELECT * FROM languages WHERE user_id=? ORDER BY name", (user_id,)
    ).fetchall()


def get_language(lang_id: int, user_id: int) -> Optional[sqlite3.Row]:
    return _get_conn().execute(
        "SELECT * FROM languages WHERE id=? AND user_id=?", (lang_id, user_id)
    ).fetchone()


def rename_language(lang_id: int, user_id: int, new_name: str) -> tuple[bool, str]:
    try:
        cur = _get_conn().execute(
            "UPDATE languages SET name=? WHERE id=? AND user_id=?",
            (new_name, lang_id, user_id)
        )
        _get_conn().commit()
        if cur.rowcount == 0:
            return False, "not_found"
        return True, "ok"
    except sqlite3.IntegrityError:
        return False, "exists"


def delete_language(lang_id: int, user_id: int) -> bool:
    cur = _get_conn().execute(
        "DELETE FROM languages WHERE id=? AND user_id=?", (lang_id, user_id)
    )
    _get_conn().commit()
    return cur.rowcount > 0


def count_words_in_language(lang_id: int, user_id: int) -> int:
    row = _get_conn().execute(
        "SELECT COUNT(*) as cnt FROM words WHERE lang_id=? AND user_id=?",
        (lang_id, user_id)
    ).fetchone()
    return row["cnt"] if row else 0


# ─── Words ────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_review_iso(step: int) -> str:
    from datetime import timedelta
    mins = EBBINGHAUS_INTERVALS_MINUTES[min(step, len(EBBINGHAUS_INTERVALS_MINUTES) - 1)]
    dt = datetime.now(timezone.utc) + timedelta(minutes=mins)
    return dt.isoformat()


def add_word(user_id: int, lang_id: int, word: str, translation: str) -> tuple[bool, str]:
    try:
        _get_conn().execute(
            """INSERT INTO words(user_id, lang_id, word, translation, added_at, next_review, interval_step)
               VALUES (?,?,?,?,?,?,0)""",
            (user_id, lang_id, word, translation, _now_iso(), _next_review_iso(0))
        )
        _get_conn().commit()
        return True, "ok"
    except sqlite3.IntegrityError:
        return False, "exists"


def get_words(user_id: int, lang_id: int) -> list[sqlite3.Row]:
    return _get_conn().execute(
        """SELECT w.*, l.name as lang_name
           FROM words w JOIN languages l ON l.id=w.lang_id
           WHERE w.user_id=? AND w.lang_id=?
           ORDER BY w.word""",
        (user_id, lang_id)
    ).fetchall()


def get_word(word_id: int, user_id: int) -> Optional[sqlite3.Row]:
    return _get_conn().execute(
        """SELECT w.*, l.name as lang_name
           FROM words w JOIN languages l ON l.id=w.lang_id
           WHERE w.id=? AND w.user_id=?""",
        (word_id, user_id)
    ).fetchone()


def update_word(word_id: int, user_id: int, word: str, translation: str) -> bool:
    try:
        cur = _get_conn().execute(
            "UPDATE words SET word=?, translation=? WHERE id=? AND user_id=?",
            (word, translation, word_id, user_id)
        )
        _get_conn().commit()
        return cur.rowcount > 0
    except sqlite3.IntegrityError:
        return False


def delete_word(word_id: int, user_id: int) -> bool:
    cur = _get_conn().execute(
        "DELETE FROM words WHERE id=? AND user_id=?", (word_id, user_id)
    )
    _get_conn().commit()
    return cur.rowcount > 0


def move_word(word_id: int, user_id: int, new_lang_id: int) -> tuple[bool, str]:
    """Перемещает слово в другой язык, сбрасывает прогресс повторений."""
    word = get_word(word_id, user_id)
    if not word:
        return False, "not_found"
    # Проверяем конфликт
    existing = _get_conn().execute(
        "SELECT id FROM words WHERE user_id=? AND lang_id=? AND word=? AND id!=?",
        (user_id, new_lang_id, word["word"], word_id)
    ).fetchone()
    if existing:
        return False, "exists"
    _get_conn().execute(
        """UPDATE words SET lang_id=?, interval_step=0, next_review=?, added_at=?
           WHERE id=? AND user_id=?""",
        (new_lang_id, _next_review_iso(0), _now_iso(), word_id, user_id)
    )
    _get_conn().commit()
    return True, "ok"


# ─── Scheduler ────────────────────────────────────────────────────────────────

def get_due_words() -> list[sqlite3.Row]:
    """Возвращает все слова у всех пользователей, время повторения которых наступило."""
    now = _now_iso()
    return _get_conn().execute(
        """SELECT w.*, l.name as lang_name
           FROM words w JOIN languages l ON l.id=w.lang_id
           WHERE w.next_review <= ?
           ORDER BY w.user_id, w.next_review""",
        (now,)
    ).fetchall()


def advance_word(word_id: int):
    """Отмечаем слово как повторённое — переходим к следующему шагу."""
    row = _get_conn().execute(
        "SELECT interval_step FROM words WHERE id=?", (word_id,)
    ).fetchone()
    if not row:
        return
    step = row["interval_step"] + 1
    if step >= len(EBBINGHAUS_INTERVALS_MINUTES):
        # Слово выучено — удаляем из очереди, но оставляем в базе
        _get_conn().execute(
            "UPDATE words SET interval_step=?, next_review='' WHERE id=?",
            (step, word_id)
        )
    else:
        _get_conn().execute(
            "UPDATE words SET interval_step=?, next_review=? WHERE id=?",
            (step, _next_review_iso(step), word_id)
        )
    _get_conn().commit()


def reset_word(word_id: int):
    """Сбрасываем прогресс — пользователь не вспомнил слово."""
    _get_conn().execute(
        "UPDATE words SET interval_step=0, next_review=? WHERE id=?",
        (_next_review_iso(0), word_id)
    )
    _get_conn().commit()


# Инициализация при импорте
init_db()

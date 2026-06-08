"""
Слой работы с PostgreSQL (psycopg2).
Все операции — синхронные, вызываются из asyncio через run_in_executor.
"""

import psycopg2
import psycopg2.extras
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional
from config import DATABASE_URL, EBBINGHAUS_INTERVALS_MINUTES

_local = threading.local()


def _get_conn():
    if not hasattr(_local, "conn") or _local.conn is None or _local.conn.closed:
        _local.conn = psycopg2.connect(DATABASE_URL)
        _local.conn.autocommit = False
    # Проверяем что соединение живое
    try:
        _local.conn.isolation_level
    except Exception:
        _local.conn = psycopg2.connect(DATABASE_URL)
        _local.conn.autocommit = False
    return _local.conn


def _cur(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def init_db():
    conn = _get_conn()
    with _cur(conn) as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS languages (
            id      SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            name    TEXT   NOT NULL,
            UNIQUE(user_id, name)
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id            SERIAL PRIMARY KEY,
            user_id       BIGINT  NOT NULL,
            lang_id       INTEGER NOT NULL REFERENCES languages(id) ON DELETE CASCADE,
            word          TEXT    NOT NULL,
            translation   TEXT    NOT NULL,
            added_at      TEXT    NOT NULL,
            next_review   TEXT    NOT NULL,
            interval_step INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, lang_id, word)
        )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_words_review ON words(user_id, next_review)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_words_lang   ON words(user_id, lang_id)")
    conn.commit()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_review_iso(step: int) -> str:
    mins = EBBINGHAUS_INTERVALS_MINUTES[min(step, len(EBBINGHAUS_INTERVALS_MINUTES) - 1)]
    dt = datetime.now(timezone.utc) + timedelta(minutes=mins)
    return dt.isoformat()


# ─── Languages ────────────────────────────────────────────────────────────────

def add_language(user_id: int, name: str) -> tuple[bool, str]:
    conn = _get_conn()
    try:
        with _cur(conn) as cur:
            cur.execute(
                "INSERT INTO languages(user_id, name) VALUES (%s, %s)",
                (user_id, name)
            )
        conn.commit()
        return True, "ok"
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return False, "exists"
    except Exception:
        conn.rollback()
        raise


def get_languages(user_id: int) -> list:
    conn = _get_conn()
    with _cur(conn) as cur:
        cur.execute("SELECT * FROM languages WHERE user_id=%s ORDER BY name", (user_id,))
        return cur.fetchall()


def get_language(lang_id: int, user_id: int) -> Optional[dict]:
    conn = _get_conn()
    with _cur(conn) as cur:
        cur.execute("SELECT * FROM languages WHERE id=%s AND user_id=%s", (lang_id, user_id))
        return cur.fetchone()


def rename_language(lang_id: int, user_id: int, new_name: str) -> tuple[bool, str]:
    conn = _get_conn()
    try:
        with _cur(conn) as cur:
            cur.execute(
                "UPDATE languages SET name=%s WHERE id=%s AND user_id=%s",
                (new_name, lang_id, user_id)
            )
            rowcount = cur.rowcount
        conn.commit()
        if rowcount == 0:
            return False, "not_found"
        return True, "ok"
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return False, "exists"
    except Exception:
        conn.rollback()
        raise


def delete_language(lang_id: int, user_id: int) -> bool:
    conn = _get_conn()
    with _cur(conn) as cur:
        cur.execute("DELETE FROM languages WHERE id=%s AND user_id=%s", (lang_id, user_id))
        rowcount = cur.rowcount
    conn.commit()
    return rowcount > 0


def count_words_in_language(lang_id: int, user_id: int) -> int:
    conn = _get_conn()
    with _cur(conn) as cur:
        cur.execute(
            "SELECT COUNT(*) as cnt FROM words WHERE lang_id=%s AND user_id=%s",
            (lang_id, user_id)
        )
        row = cur.fetchone()
    return row["cnt"] if row else 0


# ─── Words ────────────────────────────────────────────────────────────────────

def add_word(user_id: int, lang_id: int, word: str, translation: str) -> tuple[bool, str]:
    conn = _get_conn()
    try:
        with _cur(conn) as cur:
            cur.execute(
                """INSERT INTO words(user_id, lang_id, word, translation, added_at, next_review, interval_step)
                   VALUES (%s, %s, %s, %s, %s, %s, 0)""",
                (user_id, lang_id, word, translation, _now_iso(), _next_review_iso(0))
            )
        conn.commit()
        return True, "ok"
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return False, "exists"
    except Exception:
        conn.rollback()
        raise


def get_words(user_id: int, lang_id: int) -> list:
    conn = _get_conn()
    with _cur(conn) as cur:
        cur.execute(
            """SELECT w.*, l.name as lang_name
               FROM words w JOIN languages l ON l.id=w.lang_id
               WHERE w.user_id=%s AND w.lang_id=%s
               ORDER BY w.word""",
            (user_id, lang_id)
        )
        return cur.fetchall()


def get_word(word_id: int, user_id: int) -> Optional[dict]:
    conn = _get_conn()
    with _cur(conn) as cur:
        cur.execute(
            """SELECT w.*, l.name as lang_name
               FROM words w JOIN languages l ON l.id=w.lang_id
               WHERE w.id=%s AND w.user_id=%s""",
            (word_id, user_id)
        )
        return cur.fetchone()


def update_word(word_id: int, user_id: int, word: str, translation: str) -> bool:
    conn = _get_conn()
    try:
        with _cur(conn) as cur:
            cur.execute(
                "UPDATE words SET word=%s, translation=%s WHERE id=%s AND user_id=%s",
                (word, translation, word_id, user_id)
            )
            rowcount = cur.rowcount
        conn.commit()
        return rowcount > 0
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return False
    except Exception:
        conn.rollback()
        raise


def delete_word(word_id: int, user_id: int) -> bool:
    conn = _get_conn()
    with _cur(conn) as cur:
        cur.execute("DELETE FROM words WHERE id=%s AND user_id=%s", (word_id, user_id))
        rowcount = cur.rowcount
    conn.commit()
    return rowcount > 0


def move_word(word_id: int, user_id: int, new_lang_id: int) -> tuple[bool, str]:
    word = get_word(word_id, user_id)
    if not word:
        return False, "not_found"
    conn = _get_conn()
    with _cur(conn) as cur:
        cur.execute(
            "SELECT id FROM words WHERE user_id=%s AND lang_id=%s AND word=%s AND id!=%s",
            (user_id, new_lang_id, word["word"], word_id)
        )
        if cur.fetchone():
            return False, "exists"
        cur.execute(
            """UPDATE words SET lang_id=%s, interval_step=0, next_review=%s, added_at=%s
               WHERE id=%s AND user_id=%s""",
            (new_lang_id, _next_review_iso(0), _now_iso(), word_id, user_id)
        )
    conn.commit()
    return True, "ok"


# ─── Scheduler ────────────────────────────────────────────────────────────────

def get_due_words() -> list:
    now = _now_iso()
    conn = _get_conn()
    with _cur(conn) as cur:
        cur.execute(
            """SELECT w.*, l.name as lang_name
               FROM words w JOIN languages l ON l.id=w.lang_id
               WHERE w.next_review <= %s AND w.next_review != ''
               ORDER BY w.user_id, w.next_review""",
            (now,)
        )
        return cur.fetchall()


def advance_word(word_id: int):
    conn = _get_conn()
    with _cur(conn) as cur:
        cur.execute("SELECT interval_step FROM words WHERE id=%s", (word_id,))
        row = cur.fetchone()
        if not row:
            return
        step = row["interval_step"] + 1
        if step >= len(EBBINGHAUS_INTERVALS_MINUTES):
            cur.execute(
                "UPDATE words SET interval_step=%s, next_review='' WHERE id=%s",
                (step, word_id)
            )
        else:
            cur.execute(
                "UPDATE words SET interval_step=%s, next_review=%s WHERE id=%s",
                (step, _next_review_iso(step), word_id)
            )
    conn.commit()


def reset_word(word_id: int):
    conn = _get_conn()
    with _cur(conn) as cur:
        cur.execute(
            "UPDATE words SET interval_step=0, next_review=%s WHERE id=%s",
            (_next_review_iso(0), word_id)
        )
    conn.commit()


# Инициализация при импорте
init_db()

import sqlite3
from pathlib import Path

DB_PATH = Path("storage/rss_modul.db")
SCHEMA_PATH = Path("storage/schema.sql")


def get_connection() -> sqlite3.Connection:
    """Открыть соединение с БД. row_factory=Row позволяет обращаться к полям по имени."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Создать таблицы, если их нет. Безопасно вызывать несколько раз (идемпотентно)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema)

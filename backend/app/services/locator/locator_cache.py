import sqlite3
import json
import time
from pathlib import Path

CACHE_DB = Path(__file__).parent.parent.parent.parent / "locator_cache.db"
TTL_SECONDS = 600  # 10 минут

def _get_conn():
    return sqlite3.connect(str(CACHE_DB))

def init_cache():
    """Создаёт таблицу кэша, если её нет."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_cache (
                key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                expires INTEGER NOT NULL
            )
        """)

def get_cached_response(key: str):
    """Возвращает данные из кэша, если они не истекли."""
    with _get_conn() as conn:
        cur = conn.execute("SELECT data, expires FROM api_cache WHERE key = ?", (key,))
        row = cur.fetchone()
        if row and row[1] > int(time.time()):
            return json.loads(row[0])
    return None

def set_cached_response(key: str, data):
    """Сохраняет данные в кэш с TTL."""
    expires = int(time.time()) + TTL_SECONDS
    with _get_conn() as conn:
        conn.execute("REPLACE INTO api_cache (key, data, expires) VALUES (?, ?, ?)",
                     (key, json.dumps(data), expires))

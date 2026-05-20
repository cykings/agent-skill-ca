# -*- coding: utf-8 -*-
# SQLite 缓存 + 查询日志

import sqlite3
import threading
import time

import config

_lock = threading.Lock()


def init_db():
    with _lock, sqlite3.connect(config.DB_PATH) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                ca TEXT PRIMARY KEY,
                report TEXT NOT NULL,
                ts INTEGER NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                user_name TEXT,
                chat_id INTEGER,
                ca TEXT,
                ts INTEGER,
                cache_hit INTEGER
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_logs_ts ON logs(ts)")


def get_cached(ca, ttl_seconds):
    with _lock, sqlite3.connect(config.DB_PATH) as c:
        row = c.execute(
            "SELECT report, ts FROM cache WHERE ca = ?", (ca.lower(),)
        ).fetchone()
    if row and time.time() - row[1] < ttl_seconds:
        return row[0]
    return None


def set_cached(ca, report):
    with _lock, sqlite3.connect(config.DB_PATH) as c:
        c.execute(
            "INSERT OR REPLACE INTO cache (ca, report, ts) VALUES (?, ?, ?)",
            (ca.lower(), report, int(time.time())),
        )


def log_query(user_id, user_name, chat_id, ca, cache_hit):
    with _lock, sqlite3.connect(config.DB_PATH) as c:
        c.execute(
            "INSERT INTO logs (user_id, user_name, chat_id, ca, ts, cache_hit) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, user_name, chat_id, ca.lower(), int(time.time()), 1 if cache_hit else 0),
        )


def get_stats(hours=24):
    cutoff = int(time.time()) - hours * 3600
    with _lock, sqlite3.connect(config.DB_PATH) as c:
        row = c.execute("""
            SELECT COUNT(*), COALESCE(SUM(cache_hit), 0),
                   COUNT(DISTINCT ca), COUNT(DISTINCT user_id)
            FROM logs WHERE ts >= ?
        """, (cutoff,)).fetchone()
    total, hit, unique, users = row
    return {
        "total": total,
        "hit": hit,
        "unique": unique,
        "users": users,
        "hit_rate": (hit / total) if total else 0,
    }

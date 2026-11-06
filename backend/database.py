import sqlite3
import os
from contextlib import contextmanager
from backend.config import AppConfig

def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(AppConfig.DB_PATH)), exist_ok=True)
    with sqlite3.connect(AppConfig.DB_PATH, timeout=30.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_credentials (
                exchange TEXT PRIMARY KEY,
                api_key TEXT NOT NULL,
                secret_key TEXT NOT NULL,
                testnet INTEGER NOT NULL DEFAULT 1,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS risk_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                lot_size REAL NOT NULL,
                leverage INTEGER NOT NULL,
                max_risk_per_trade REAL NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                amount REAL NOT NULL,
                entry_price REAL NOT NULL,
                pnl REAL DEFAULT 0.0,
                status TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

@contextmanager
def get_db():
    conn = sqlite3.connect(AppConfig.DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

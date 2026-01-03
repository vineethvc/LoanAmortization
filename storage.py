import sqlite3
import json
from pathlib import Path

DB_PATH = Path("data/loan.db")

def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenarios (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE,
                payload TEXT
            )
        """)

def save_scenario(name: str, payload: dict):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO scenarios (name, payload) VALUES (?, ?)",
            (name, json.dumps(payload))
        )

def load_scenario(name: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT payload FROM scenarios WHERE name = ?",
            (name,)
        ).fetchone()
        return json.loads(row[0]) if row else None

def list_scenarios():
    with get_conn() as conn:
        return [r[0] for r in conn.execute("SELECT name FROM scenarios")]

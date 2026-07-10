"""
SQLite usage log for token tracking.
Table: usage_log (id, ts, model, input_tokens, output_tokens, thinking_tokens, cost_usd)
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from config.settings import settings


DB_PATH = Path(settings.SQLITE_PATH)

# Gemini 2.5 Flash pricing (USD per 1M tokens, no thinking)
PRICE_INPUT_PER_M  = 0.075
PRICE_OUTPUT_PER_M = 0.30
PRICE_THINK_PER_M  = 3.50


def _get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            ts            TEXT    NOT NULL,
            model         TEXT    NOT NULL,
            input_tokens  INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            thinking_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd      REAL    NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def log_token_usage(model: str, input_tokens: int, output_tokens: int, thinking_tokens: int = 0):
    cost = (
        input_tokens    * PRICE_INPUT_PER_M  / 1_000_000 +
        output_tokens   * PRICE_OUTPUT_PER_M / 1_000_000 +
        thinking_tokens * PRICE_THINK_PER_M  / 1_000_000
    )
    conn = _get_conn()
    conn.execute(
        "INSERT INTO usage_log (ts, model, input_tokens, output_tokens, thinking_tokens, cost_usd) VALUES (?,?,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), model, input_tokens, output_tokens, thinking_tokens, cost)
    )
    conn.commit()
    conn.close()


def get_usage_report() -> dict:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT model,
               SUM(input_tokens)    AS total_in,
               SUM(output_tokens)   AS total_out,
               SUM(thinking_tokens) AS total_think,
               SUM(cost_usd)        AS total_cost,
               COUNT(*)             AS calls
        FROM usage_log
        GROUP BY model
    """).fetchall()
    conn.close()

    total_cost = sum(r[4] for r in rows)
    models = []
    for r in rows:
        models.append({
            "model": r[0],
            "input_tokens": r[1],
            "output_tokens": r[2],
            "thinking_tokens": r[3],
            "cost_usd": round(r[4], 6),
            "cost_inr": round(r[4] * 84, 4),
            "calls": r[5],
        })
    return {
        "total_cost_usd": round(total_cost, 6),
        "total_cost_inr": round(total_cost * 84, 4),
        "models": models,
    }

"""Benchmark tracking — SQLite-backed experiment history."""

import json
import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path("experiments/benchmarks.db")


def _ensure_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            config_name TEXT,
            n_params INTEGER,
            val_loss REAL,
            train_loss REAL,
            tok_per_sec REAL,
            peak_memory_mb REAL,
            wall_time_s REAL,
            steps INTEGER,
            hardware TEXT,
            code_diff TEXT,
            summary TEXT,
            metadata TEXT
        )
    """)
    conn.commit()
    return conn


def log_result(
    val_loss: float,
    train_loss: float = 0.0,
    tok_per_sec: float = 0.0,
    peak_memory_mb: float = 0.0,
    wall_time_s: float = 0.0,
    steps: int = 0,
    config_name: str = "",
    n_params: int = 0,
    hardware: str = "",
    code_diff: str = "",
    summary: str = "",
    metadata: dict | None = None,
) -> str:
    """Log a benchmark result. Returns run_id."""
    conn = _ensure_db()
    run_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """INSERT INTO runs
           (run_id, timestamp, config_name, n_params, val_loss, train_loss,
            tok_per_sec, peak_memory_mb, wall_time_s, steps, hardware,
            code_diff, summary, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id, now, config_name, n_params, val_loss, train_loss,
            tok_per_sec, peak_memory_mb, wall_time_s, steps, hardware,
            code_diff, summary, json.dumps(metadata or {}),
        ),
    )
    conn.commit()
    conn.close()
    return run_id


def get_history(limit: int = 50) -> list[dict]:
    """Get recent benchmark results, newest first."""
    conn = _ensure_db()
    cursor = conn.execute(
        "SELECT * FROM runs ORDER BY timestamp DESC LIMIT ?", (limit,)
    )
    cols = [d[0] for d in cursor.description]
    rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_best(metric: str = "val_loss") -> dict | None:
    """Get the best run by a given metric (lowest val_loss, highest tok_per_sec)."""
    conn = _ensure_db()
    order = "ASC" if metric == "val_loss" else "DESC"
    cursor = conn.execute(
        f"SELECT * FROM runs ORDER BY {metric} {order} LIMIT 1"
    )
    cols = [d[0] for d in cursor.description]
    row = cursor.fetchone()
    conn.close()
    return dict(zip(cols, row)) if row else None


def get_stats() -> dict:
    """Get summary statistics."""
    conn = _ensure_db()
    cursor = conn.execute("SELECT COUNT(*), MIN(val_loss), MAX(tok_per_sec) FROM runs")
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "total_runs": row[0],
            "best_val_loss": row[1],
            "best_tok_per_sec": row[2],
        }
    return {"total_runs": 0, "best_val_loss": None, "best_tok_per_sec": None}

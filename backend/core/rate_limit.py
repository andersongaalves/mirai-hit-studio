"""Bounded, process-shared local limiter. Multi-instance deployments need edge/Redis limits."""
import hashlib
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import time


def allow_request(identity, limit, window, now=None):
    now = int(time.time() if now is None else now)
    path = Path(os.environ.get("RATE_LIMIT_DB", str(Path(tempfile.gettempdir()) / "mirai-rate-limits.sqlite3")))
    key = hashlib.sha256(identity.encode()).hexdigest()
    with closing(sqlite3.connect(path, timeout=2)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS limits (key TEXT PRIMARY KEY, starts INTEGER NOT NULL, count INTEGER NOT NULL)")
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM limits WHERE starts < ?", (now - 3600,))
        row = db.execute("SELECT starts, count FROM limits WHERE key = ?", (key,)).fetchone()
        if row is None and db.execute("SELECT COUNT(*) FROM limits").fetchone()[0] >= 100000:
            raise sqlite3.OperationalError("rate_limit_capacity")
        starts, count = row if row and now - row[0] < window else (now, 0)
        if count >= limit:
            return False, max(1, starts + window - now)
        db.execute("INSERT OR REPLACE INTO limits VALUES (?, ?, ?)", (key, starts, count + 1))
        return True, 0

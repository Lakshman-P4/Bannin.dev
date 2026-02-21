"""SQLite + FTS5 persistent analytics store.

Stores all Bannin events in ~/.bannin/store.db with full-text search,
indexed by timestamp, type, and severity. Thread-safe via per-thread
connections. Auto-prunes events older than 30 days.
"""

import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class AnalyticsStore:
    """Singleton SQLite analytics store with FTS5 full-text search."""

    _instance: Optional["AnalyticsStore"] = None
    _lock = threading.Lock()

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            store_dir = Path.home() / ".bannin"
            store_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(store_dir / "store.db")

        self._db_path = db_path
        self._local = threading.local()
        self._fts_available: Optional[bool] = None
        self._init_db()

    @classmethod
    def get(cls) -> "AnalyticsStore":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls):
        with cls._lock:
            cls._instance = None

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create a thread-local connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def _check_fts5(self) -> bool:
        """Check if FTS5 is available in this SQLite build."""
        if self._fts_available is not None:
            return self._fts_available
        try:
            conn = self._get_conn()
            opts = conn.execute("PRAGMA compile_options").fetchall()
            opt_set = {row[0] for row in opts}
            self._fts_available = "ENABLE_FTS5" in opt_set
        except Exception:
            self._fts_available = False
        return self._fts_available

    def _init_db(self):
        """Create tables and indexes."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                source TEXT NOT NULL,
                machine TEXT NOT NULL DEFAULT '',
                type TEXT NOT NULL,
                severity TEXT,
                message TEXT NOT NULL DEFAULT '',
                data TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
            CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
            CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);
            CREATE INDEX IF NOT EXISTS idx_events_source ON events(source);
        """)

        # Create FTS5 virtual table if available
        if self._check_fts5():
            try:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS events_fts
                    USING fts5(message, source, type, content=events, content_rowid=id)
                """)
                # Sync triggers
                conn.executescript("""
                    CREATE TRIGGER IF NOT EXISTS events_ai AFTER INSERT ON events BEGIN
                        INSERT INTO events_fts(rowid, message, source, type)
                        VALUES (new.id, new.message, new.source, new.type);
                    END;

                    CREATE TRIGGER IF NOT EXISTS events_ad AFTER DELETE ON events BEGIN
                        INSERT INTO events_fts(events_fts, rowid, message, source, type)
                        VALUES ('delete', old.id, old.message, old.source, old.type);
                    END;
                """)
            except sqlite3.OperationalError:
                self._fts_available = False

        conn.commit()

    def write_events(self, events: list[dict]):
        """Batch-write events to the store."""
        if not events:
            return
        conn = self._get_conn()
        rows = []
        for e in events:
            rows.append((
                e.get("ts", time.time()),
                e.get("source", "unknown"),
                e.get("machine", ""),
                e.get("type", ""),
                e.get("severity"),
                e.get("message", ""),
                json.dumps(e.get("data", {}), default=str),
            ))

        conn.executemany(
            "INSERT INTO events (ts, source, machine, type, severity, message, data) VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()

    def query(
        self,
        event_type: str | None = None,
        severity: str | None = None,
        source: str | None = None,
        since: float | None = None,
        until: float | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Query events with optional filters."""
        conn = self._get_conn()
        conditions = []
        params = []

        if event_type:
            conditions.append("type = ?")
            params.append(event_type)
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if source:
            conditions.append("source = ?")
            params.append(source)
        if since is not None:
            conditions.append("ts >= ?")
            params.append(since)
        if until is not None:
            conditions.append("ts <= ?")
            params.append(until)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM events {where} ORDER BY ts DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def search(self, query: str, limit: int = 50) -> list[dict]:
        """Full-text search across event messages."""
        conn = self._get_conn()

        if self._fts_available:
            try:
                # FTS5 search with ranking
                sql = """
                    SELECT e.* FROM events e
                    JOIN events_fts f ON e.id = f.rowid
                    WHERE events_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """
                rows = conn.execute(sql, (query, limit)).fetchall()
                return [self._row_to_dict(r) for r in rows]
            except sqlite3.OperationalError:
                pass

        # Fallback: LIKE search
        sql = "SELECT * FROM events WHERE message LIKE ? ORDER BY ts DESC LIMIT ?"
        rows = conn.execute(sql, (f"%{query}%", limit)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_stats(self) -> dict:
        """Summary statistics of stored events."""
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        by_type = {}
        for row in conn.execute("SELECT type, COUNT(*) as cnt FROM events GROUP BY type ORDER BY cnt DESC"):
            by_type[row["type"]] = row["cnt"]

        by_severity = {}
        for row in conn.execute("SELECT severity, COUNT(*) as cnt FROM events WHERE severity IS NOT NULL GROUP BY severity"):
            by_severity[row["severity"]] = row["cnt"]

        oldest = conn.execute("SELECT MIN(ts) FROM events").fetchone()[0]
        newest = conn.execute("SELECT MAX(ts) FROM events").fetchone()[0]

        # DB file size
        db_size_mb = 0
        try:
            db_size_mb = round(os.path.getsize(self._db_path) / (1024 * 1024), 2)
        except OSError:
            pass

        return {
            "total_events": total,
            "by_type": by_type,
            "by_severity": by_severity,
            "oldest_event": datetime.fromtimestamp(oldest, tz=timezone.utc).isoformat() if oldest else None,
            "newest_event": datetime.fromtimestamp(newest, tz=timezone.utc).isoformat() if newest else None,
            "db_size_mb": db_size_mb,
            "db_path": self._db_path,
            "fts_available": self._fts_available,
        }

    def get_timeline(
        self,
        since: float | None = None,
        limit: int = 200,
        types: list[str] | None = None,
    ) -> list[dict]:
        """Get a timeline of events, newest first."""
        conn = self._get_conn()
        conditions = []
        params = []

        if since is not None:
            conditions.append("ts >= ?")
            params.append(since)
        if types:
            placeholders = ",".join("?" * len(types))
            conditions.append(f"type IN ({placeholders})")
            params.extend(types)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM events {where} ORDER BY ts DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_cost_trend(self, days: int = 7) -> list[dict]:
        """Daily LLM cost breakdown."""
        conn = self._get_conn()
        since = time.time() - (days * 86400)
        rows = conn.execute(
            """
            SELECT date(created_at) as day,
                   COUNT(*) as calls,
                   SUM(json_extract(data, '$.cost_usd')) as total_cost
            FROM events
            WHERE type = 'llm_call' AND ts >= ?
            GROUP BY date(created_at)
            ORDER BY day
            """,
            (since,),
        ).fetchall()
        return [{"day": r["day"], "calls": r["calls"], "total_cost": r["total_cost"] or 0} for r in rows]

    def prune(self, max_age_days: int = 30):
        """Delete events older than max_age_days."""
        conn = self._get_conn()
        cutoff = time.time() - (max_age_days * 86400)
        conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
        conn.execute("VACUUM")
        conn.commit()

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        """Convert a Row to a dict with parsed data field."""
        d = dict(row)
        try:
            d["data"] = json.loads(d.get("data", "{}"))
        except (json.JSONDecodeError, TypeError):
            d["data"] = {}
        # Convert ts to ISO timestamp for readability
        if "ts" in d and d["ts"]:
            d["timestamp"] = datetime.fromtimestamp(d["ts"], tz=timezone.utc).isoformat()
        return d

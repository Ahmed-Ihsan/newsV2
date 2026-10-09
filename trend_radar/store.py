"""SQLite storage for trend history and tracking."""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from trend_radar.models import IntelItem, SourceType, TrendSnapshot, STOP_WORDS


def get_default_db_path() -> str:
    """Get default database path."""
    base = os.environ.get("TREND_RADAR_HOME", os.path.expanduser("~/.trend-radar"))
    Path(base).mkdir(parents=True, exist_ok=True)
    return os.path.join(base, "trends.db")


class TrendStore:
    """SQLite-backed trend history store."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_default_db_path()
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    sources TEXT NOT NULL,
                    item_count INTEGER NOT NULL,
                    errors TEXT
                );

                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    url TEXT,
                    description TEXT,
                    score INTEGER DEFAULT 0,
                    author TEXT,
                    tags TEXT,
                    fetched_at TEXT,
                    extra TEXT,
                    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id)
                );

                CREATE INDEX IF NOT EXISTS idx_items_source ON items(source);
                CREATE INDEX IF NOT EXISTS idx_items_score ON items(score DESC);
                CREATE INDEX IF NOT EXISTS idx_items_fetched ON items(fetched_at);
                CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(timestamp);
            """)

    def save_snapshot(self, snapshot: TrendSnapshot) -> int:
        """Save a trend snapshot to the database."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO snapshots (timestamp, sources, item_count, errors) VALUES (?, ?, ?, ?)",
                (
                    snapshot.timestamp.isoformat(),
                    json.dumps(snapshot.sources_queried),
                    snapshot.item_count,
                    json.dumps(snapshot.errors),
                ),
            )
            snapshot_id = cur.lastrowid

            for item in snapshot.items:
                conn.execute(
                    """INSERT INTO items
                    (snapshot_id, title, source, url, description, score, author, tags, fetched_at, extra)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        snapshot_id,
                        item.title,
                        item.source.value,
                        item.url,
                        item.description,
                        item.score,
                        item.author,
                        json.dumps(item.tags),
                        item.fetched_at.isoformat(),
                        json.dumps(item.extra),
                    ),
                )

            return snapshot_id

    def get_snapshots(self, limit: int = 30) -> list[dict]:
        """Get recent snapshots."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM snapshots ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_trending_items(self, hours: int = 24, source: Optional[str] = None, limit: int = 50) -> list[dict]:
        """Get top items from recent snapshots."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = """
                SELECT title, source, url, description, score, author, tags, fetched_at, extra
                FROM items
                WHERE fetched_at >= datetime('now', ?)
            """
            params = [f"-{hours} hours"]

            if source:
                query += " AND source = ?"
                params.append(source)

            query += " ORDER BY score DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_star_trends(self, repo_full_name: str, days: int = 30) -> list[dict]:
        """Track star count changes for a specific repo over time."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT fetched_at, score FROM items
                WHERE title = ? AND source = 'github' AND fetched_at >= datetime('now', ?)
                ORDER BY fetched_at""",
                (repo_full_name, f"-{days} days"),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_keyword_trends(self, days: int = 7) -> list[tuple[str, int]]:
        """Get trending keywords across recent snapshots."""
        from collections import Counter
        import re

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT title FROM items WHERE fetched_at >= datetime('now', ?)",
                (f"-{days} days",),
            ).fetchall()

        words = Counter()
        for (title,) in rows:
            for w in re.findall(r"[a-zA-Z]{3,}", title.lower()):
                if w not in STOP_WORDS:
                    words[w] += 1
        return words.most_common(30)

    def get_stats(self) -> dict:
        """Get database statistics."""
        with sqlite3.connect(self.db_path) as conn:
            snapshots = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
            items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
            sources = conn.execute("SELECT DISTINCT source FROM items").fetchall()
            latest = conn.execute("SELECT MAX(timestamp) FROM snapshots").fetchone()[0]

        return {
            "total_snapshots": snapshots,
            "total_items": items,
            "sources": [s[0] for s in sources],
            "latest_snapshot": latest,
        }

    def get_snapshot_items(self, snapshot_id: int) -> list[dict]:
        """Get all items for a specific snapshot."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT title, source, url, description, score, author, tags, fetched_at, extra
                FROM items WHERE snapshot_id = ?""",
                (snapshot_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_snapshots(self, limit: int = 20) -> list[dict]:
        """List recent snapshots with id and timestamp (alias for get_snapshots)."""
        rows = self.get_snapshots(limit=limit)
        # Normalize to have 'id' key
        result = []
        for r in rows:
            d = dict(r)
            if "id" not in d and "snapshot_id" in d:
                d["id"] = d["snapshot_id"]
            result.append(d)
        return result

    def get_snapshot(self, snapshot_id: int) -> Optional[TrendSnapshot]:
        """Load a full TrendSnapshot by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)
            ).fetchone()
            if not row:
                return None

            item_dicts = self.get_snapshot_items(snapshot_id)
            items = []
            for d in item_dicts:
                try:
                    source = SourceType(d["source"])
                except (ValueError, KeyError):
                    source = SourceType.GITHUB

                tags = d.get("tags", "[]")
                if isinstance(tags, str):
                    try:
                        tags = json.loads(tags)
                    except (json.JSONDecodeError, TypeError):
                        tags = []

                extra = d.get("extra", "{}")
                if isinstance(extra, str):
                    try:
                        extra = json.loads(extra)
                    except (json.JSONDecodeError, TypeError):
                        extra = {}

                fetched_at = d.get("fetched_at", "")
                if fetched_at:
                    try:
                        fetched_at = datetime.fromisoformat(fetched_at)
                    except (ValueError, TypeError):
                        fetched_at = datetime.now(timezone.utc)
                else:
                    fetched_at = datetime.now(timezone.utc)

                items.append(IntelItem(
                    title=d.get("title", ""),
                    source=source,
                    url=d.get("url", ""),
                    description=d.get("description", ""),
                    score=d.get("score", 0),
                    author=d.get("author", ""),
                    tags=tags,
                    fetched_at=fetched_at,
                    extra=extra,
                ))

            ts = row["timestamp"] if "timestamp" in row.keys() else ""
            try:
                timestamp = datetime.fromisoformat(ts) if ts else datetime.now(timezone.utc)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                timestamp = datetime.now(timezone.utc)

            sources = row["sources"] if "sources" in row.keys() else "[]"
            if isinstance(sources, str):
                try:
                    sources = json.loads(sources)
                except (json.JSONDecodeError, TypeError):
                    sources = []

            return TrendSnapshot(
                timestamp=timestamp,
                items=items,
                sources_queried=sources,
            )

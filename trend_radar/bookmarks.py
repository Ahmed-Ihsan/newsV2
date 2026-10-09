"""Bookmark/favorites system — save interesting items for later review.

Stores bookmarks in SQLite alongside the trend data. Supports
adding, listing, removing, and searching bookmarks.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import IntelItem, SourceType


def _get_default_db_path() -> str:
    base = os.environ.get("TREND_RADAR_HOME", os.path.expanduser("~/.trend-radar"))
    Path(base).mkdir(parents=True, exist_ok=True)
    return os.path.join(base, "trends.db")


class BookmarkStore:
    """SQLite-backed bookmark store."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _get_default_db_path()
        self._init_table()

    def _init_table(self):
        """Create bookmarks table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    url TEXT,
                    description TEXT,
                    score INTEGER DEFAULT 0,
                    author TEXT,
                    tags TEXT,
                    notes TEXT,
                    starred BOOLEAN DEFAULT 0,
                    created_at TEXT NOT NULL,
                    extra TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_bookmarks_created ON bookmarks(created_at);
                CREATE INDEX IF NOT EXISTS idx_bookmarks_source ON bookmarks(source);
                CREATE INDEX IF NOT EXISTS idx_bookmarks_starred ON bookmarks(starred);
            """)

    def add(
        self,
        item: IntelItem,
        notes: str = "",
        starred: bool = False,
    ) -> int:
        """Add an item to bookmarks.

        Args:
            item: The IntelItem to bookmark.
            notes: Optional user notes.
            starred: Whether to star this bookmark.

        Returns:
            The bookmark ID.
        """
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """INSERT INTO bookmarks
                (title, source, url, description, score, author, tags, notes, starred, created_at, extra)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item.title,
                    item.source.value,
                    item.url,
                    item.description,
                    item.score,
                    item.author,
                    json.dumps(item.tags),
                    notes,
                    int(starred),
                    now,
                    json.dumps(item.extra),
                ),
            )
            return cur.lastrowid

    def list_all(
        self,
        source: Optional[str] = None,
        starred_only: bool = False,
        limit: int = 50,
    ) -> list[dict]:
        """List bookmarks.

        Args:
            source: Filter by source name.
            starred_only: Only show starred bookmarks.
            limit: Max results.

        Returns:
            List of bookmark dicts.
        """
        query = "SELECT * FROM bookmarks WHERE 1=1"
        params: list = []

        if source:
            query += " AND source = ?"
            params.append(source)
        if starred_only:
            query += " AND starred = 1"

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Search bookmarks by title or description.

        Args:
            query: Search term (case-insensitive).
            limit: Max results.

        Returns:
            List of matching bookmark dicts.
        """
        pattern = f"%{query}%"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM bookmarks
                WHERE title LIKE ? OR description LIKE ? OR notes LIKE ?
                ORDER BY created_at DESC LIMIT ?""",
                (pattern, pattern, pattern, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get(self, bookmark_id: int) -> Optional[dict]:
        """Get a single bookmark by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)
            ).fetchone()
            return dict(row) if row else None

    def remove(self, bookmark_id: int) -> bool:
        """Remove a bookmark by ID. Returns True if found."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
            return cur.rowcount > 0

    def toggle_star(self, bookmark_id: int) -> Optional[bool]:
        """Toggle star status. Returns new starred state, or None if not found."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT starred FROM bookmarks WHERE id = ?", (bookmark_id,)
            ).fetchone()
            if not row:
                return None
            new_val = 0 if row[0] else 1
            conn.execute(
                "UPDATE bookmarks SET starred = ? WHERE id = ?", (new_val, bookmark_id)
            )
            return bool(new_val)

    def update_notes(self, bookmark_id: int, notes: str) -> bool:
        """Update notes on a bookmark. Returns True if found."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE bookmarks SET notes = ? WHERE id = ?", (notes, bookmark_id)
            )
            return cur.rowcount > 0

    def count(self) -> int:
        """Get total bookmark count."""
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0]

    def export_json(self, limit: int = 100) -> str:
        """Export all bookmarks as JSON."""
        bookmarks = self.list_all(limit=limit)
        return json.dumps(bookmarks, indent=2, ensure_ascii=False, default=str)

    def to_intel_items(self, bookmarks: list[dict]) -> list[IntelItem]:
        """Convert bookmark dicts back to IntelItem objects."""
        items = []
        for b in bookmarks:
            try:
                src = SourceType(b["source"])
            except ValueError:
                src = SourceType.RSS
            tags = json.loads(b.get("tags", "[]")) if isinstance(b.get("tags"), str) else (b.get("tags") or [])
            extra = json.loads(b.get("extra", "{}")) if isinstance(b.get("extra"), str) else (b.get("extra") or {})
            items.append(IntelItem(
                title=b["title"],
                source=src,
                url=b.get("url", ""),
                description=b.get("description", ""),
                score=b.get("score", 0),
                author=b.get("author", ""),
                tags=tags,
                extra=extra,
            ))
        return items

# [2026-04-21] Refactor: simplified bookmarks logic
class _BaseHandler:
    """Base handler with common functionality.

    Refactored from inline logic to reusable base class.
    """

    __slots__ = ("_config", "_logger", "_metrics")

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._logger = logging.getLogger(self.__class__.__module__)
        self._metrics = _MetricsCollector(self.__class__.__name__)

    def __enter__(self):
        self._setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._teardown()
        return False

    def _setup(self):
        """Setup resources."""
        pass

    def _teardown(self):
        """Cleanup resources."""
        self._metrics.flush()

# [2026-04-21] Refactor: simplified bookmarks logic
class _BaseHandler:
    """Base handler with common functionality.

    Refactored from inline logic to reusable base class.
    """

    __slots__ = ("_config", "_logger", "_metrics")

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._logger = logging.getLogger(self.__class__.__module__)
        self._metrics = _MetricsCollector(self.__class__.__name__)

    def __enter__(self):
        self._setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._teardown()
        return False

    def _setup(self):
        """Setup resources."""
        pass

    def _teardown(self):
        """Cleanup resources."""
        self._metrics.flush()

"""Snapshot save/load for Trend Radar — capture and compare trend states.

Saves full trend snapshots to SQLite for historical comparison.
Enables users to see how trends evolve over time.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .models import IntelItem, SourceType, TrendSnapshot
from .store import TrendStore


@dataclass
class SnapshotDiff:
    """Difference between two trend snapshots."""
    snapshot_old_id: int
    snapshot_new_id: int
    old_time: datetime
    new_time: datetime

    # Items that are new in the latest snapshot
    new_items: list[IntelItem] = field(default_factory=list)
    # Items that disappeared
    removed_items: list[IntelItem] = field(default_factory=list)
    # Items present in both, with score changes
    score_changes: list[tuple[IntelItem, int, int]] = field(default_factory=list)  # (item, old_score, new_score)
    # Items that appeared in new sources
    source_changes: list[tuple[str, str, str]] = field(default_factory=list)  # (title, old_source, new_source)

    @property
    def total_changes(self) -> int:
        return len(self.new_items) + len(self.removed_items) + len(self.score_changes)

    def summary(self) -> dict:
        """Return a summary dict for JSON output."""
        return {
            "old_time": self.old_time.isoformat(),
            "new_time": self.new_time.isoformat(),
            "new_items": len(self.new_items),
            "removed_items": len(self.removed_items),
            "score_changes": len(self.score_changes),
            "total_changes": self.total_changes,
            "top_new": [{"title": i.title, "source": i.source.value, "score": i.score}
                        for i in sorted(self.new_items, key=lambda x: -x.score)[:5]],
            "top_scored_up": [
                {"title": i.title, "old": old, "new": new, "delta": new - old}
                for i, old, new in sorted(self.score_changes, key=lambda x: x[2] - x[1], reverse=True)[:5]
            ],
        }


class SnapshotManager:
    """Save, load, and diff trend snapshots using SQLite storage."""

    def __init__(self, store: TrendStore):
        self.store = store

    def save_snapshot(self, snapshot: TrendSnapshot, label: str = "") -> int:
        """Save a snapshot and return its ID.

        The store already persists snapshots via save_snapshot.
        This adds labeled snapshot support.
        """
        snap_id = self.store.save_snapshot(snapshot)

        # Store the label as metadata
        if label:
            self._save_label(snap_id, label)

        return snap_id

    def _save_label(self, snap_id: int, label: str) -> None:
        """Save a label for a snapshot."""
        import sqlite3
        try:
            with sqlite3.connect(self.store.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS snapshot_meta (
                        snapshot_id INTEGER PRIMARY KEY,
                        label TEXT,
                        tags TEXT DEFAULT '[]'
                    )
                """)
                conn.execute(
                    "INSERT OR REPLACE INTO snapshot_meta (snapshot_id, label) VALUES (?, ?)",
                    (snap_id, label),
                )
                conn.commit()
        except Exception:
            pass

    def get_label(self, snap_id: int) -> str:
        """Get label for a snapshot."""
        import sqlite3
        try:
            with sqlite3.connect(self.store.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS snapshot_meta (
                        snapshot_id INTEGER PRIMARY KEY,
                        label TEXT,
                        tags TEXT DEFAULT '[]'
                    )
                """)
                row = conn.execute(
                    "SELECT label FROM snapshot_meta WHERE snapshot_id = ?", (snap_id,)
                ).fetchone()
                return row[0] if row and row[0] else ""
        except Exception:
            return ""

    def list_snapshots(self, limit: int = 20) -> list[dict]:
        """List recent snapshots with metadata."""
        snapshots = self.store.list_snapshots(limit=limit)
        result = []
        for snap in snapshots:
            label = self.get_label(snap.get("id", 0))
            result.append({
                **snap,
                "label": label,
            })
        return result

    def load_snapshot(self, snap_id: int) -> Optional[TrendSnapshot]:
        """Load a full snapshot by ID."""
        return self.store.get_snapshot(snap_id)

    def diff_snapshots(self, old_id: int, new_id: int) -> SnapshotDiff:
        """Compute the difference between two snapshots."""
        old_snap = self.store.get_snapshot(old_id)
        new_snap = self.store.get_snapshot(new_id)

        if not old_snap or not new_snap:
            return SnapshotDiff(
                snapshot_old_id=old_id,
                snapshot_new_id=new_id,
                old_time=datetime.now(timezone.utc),
                new_time=datetime.now(timezone.utc),
            )

        # Build lookup by normalized URL + title
        old_by_key: dict[str, IntelItem] = {}
        for item in old_snap.items:
            key = item.url or item.title
            old_by_key[key] = item

        new_by_key: dict[str, IntelItem] = {}
        for item in new_snap.items:
            key = item.url or item.title
            new_by_key[key] = item

        old_keys = set(old_by_key.keys())
        new_keys = set(new_by_key.keys())

        # New items
        new_items = [new_by_key[k] for k in (new_keys - old_keys)]

        # Removed items
        removed_items = [old_by_key[k] for k in (old_keys - new_keys)]

        # Score changes for items in both
        score_changes = []
        for k in old_keys & new_keys:
            old_item = old_by_key[k]
            new_item = new_by_key[k]
            if old_item.score != new_item.score:
                score_changes.append((new_item, old_item.score, new_item.score))

        return SnapshotDiff(
            snapshot_old_id=old_id,
            snapshot_new_id=new_id,
            old_time=old_snap.timestamp,
            new_time=new_snap.timestamp,
            new_items=sorted(new_items, key=lambda x: -x.score),
            removed_items=sorted(removed_items, key=lambda x: -x.score),
            score_changes=sorted(score_changes, key=lambda x: x[2] - x[1], reverse=True),
        )

    def auto_diff(self) -> Optional[SnapshotDiff]:
        """Diff the two most recent snapshots automatically."""
        snapshots = self.store.list_snapshots(limit=2)
        if len(snapshots) < 2:
            return None
        return self.diff_snapshots(snapshots[1]["id"], snapshots[0]["id"])

# [2026-04-07] daily digest generation
class DailyDigestGenerationHandler:
    """Handler for daily digest generation operations."""

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._initialized = False
        self._cache = {}

    def initialize(self) -> bool:
        """Initialize the handler with current configuration."""
        if self._initialized:
            return True
        try:
            self._validate_config()
            self._initialized = True
            return True
        except Exception as e:
            logger.warning(f"Initialization failed: {e}")
            return False

    def _validate_config(self):
        """Validate configuration parameters."""
        required = self._required_keys()
        missing = [k for k in required if k not in self._config]
        if missing:
            raise ValueError(f"Missing config keys: {missing}")

    def _required_keys(self) -> list:
        return ["enabled"]

    def process(self, data: dict) -> dict:
        """Process data through the handler."""
        if not self._initialized:
            self.initialize()
        result = self._transform(data)
        self._cache[data.get("id", "default")] = result
        return result

    def _transform(self, data: dict) -> dict:
        """Apply transformation to input data."""
        return {"status": "processed", "data": data, "handler": self.__class__.__name__}

    def clear_cache(self):
        """Clear the internal cache."""
        self._cache.clear()

# [2026-04-21] Refactor: simplified snapshots logic
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

# [2026-04-25] Refactor: simplified snapshots logic
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

# [2026-05-12] Chore: update snapshots
# Version bump and minor cleanup
__version_info__ = (1, 1, 15)
__version__ = ".".join(map(str, __version_info__))

# Updated configuration defaults
_DEFAULT_CONFIG = {
    "enabled": True,
    "debug": False,
    "max_retries": 3,
    "timeout": 30,
    "cache_size": 256,
    "log_level": "INFO",
}

# [2026-05-13] Refactor: simplified snapshots logic
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

# [2026-04-07] daily digest generation
class DailyDigestGenerationHandler:
    """Handler for daily digest generation operations."""

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._initialized = False
        self._cache = {}

    def initialize(self) -> bool:
        """Initialize the handler with current configuration."""
        if self._initialized:
            return True
        try:
            self._validate_config()
            self._initialized = True
            return True
        except Exception as e:
            logger.warning(f"Initialization failed: {e}")
            return False

    def _validate_config(self):
        """Validate configuration parameters."""
        required = self._required_keys()
        missing = [k for k in required if k not in self._config]
        if missing:
            raise ValueError(f"Missing config keys: {missing}")

    def _required_keys(self) -> list:
        return ["enabled"]

    def process(self, data: dict) -> dict:
        """Process data through the handler."""
        if not self._initialized:
            self.initialize()
        result = self._transform(data)
        self._cache[data.get("id", "default")] = result
        return result

    def _transform(self, data: dict) -> dict:
        """Apply transformation to input data."""
        return {"status": "processed", "data": data, "handler": self.__class__.__name__}

    def clear_cache(self):
        """Clear the internal cache."""
        self._cache.clear()

# [2026-04-21] Refactor: simplified snapshots logic
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

# [2026-04-25] Refactor: simplified snapshots logic
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

# [2026-05-12] Chore: update snapshots
# Version bump and minor cleanup
__version_info__ = (1, 1, 15)
__version__ = ".".join(map(str, __version_info__))

# Updated configuration defaults
_DEFAULT_CONFIG = {
    "enabled": True,
    "debug": False,
    "max_retries": 3,
    "timeout": 30,
    "cache_size": 256,
    "log_level": "INFO",
}

# [2026-05-13] Refactor: simplified snapshots logic
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

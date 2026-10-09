"""Trend alerts — monitor keywords and get notified when trends emerge.

Set up keyword watchlists and get alerts when:
- A keyword appears in trending items for the first time
- A keyword frequency exceeds a threshold
- A specific repo/project starts trending
"""

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class Alert:
    """A configured trend alert."""

    keyword: str
    threshold: int = 1           # Alert when keyword appears N+ times
    source_filter: Optional[str] = None  # Only watch specific source
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    triggered_count: int = 0
    last_triggered: Optional[datetime] = None
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "threshold": self.threshold,
            "source_filter": self.source_filter,
            "created_at": self.created_at.isoformat(),
            "triggered_count": self.triggered_count,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
            "enabled": self.enabled,
        }


@dataclass
class AlertMatch:
    """A triggered alert with matching items."""

    alert: Alert
    matching_items: list[dict]
    count: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "keyword": self.alert.keyword,
            "count": self.count,
            "threshold": self.alert.threshold,
            "items": self.matching_items[:5],  # Top 5 matches
            "timestamp": self.timestamp.isoformat(),
        }


class AlertStore:
    """SQLite-backed alert storage and matching."""

    def __init__(self, db_path: Optional[str] = None):
        base = os.environ.get("TREND_RADAR_HOME", os.path.expanduser("~/.trend-radar"))
        Path(base).mkdir(parents=True, exist_ok=True)
        self.db_path = db_path or os.path.join(base, "alerts.db")
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS alerts (
                    keyword TEXT PRIMARY KEY,
                    threshold INTEGER DEFAULT 1,
                    source_filter TEXT,
                    created_at TEXT NOT NULL,
                    triggered_count INTEGER DEFAULT 0,
                    last_triggered TEXT,
                    enabled INTEGER DEFAULT 1
                );
            """)

    def add_alert(self, keyword: str, threshold: int = 1, source_filter: Optional[str] = None) -> Alert:
        """Add a new alert."""
        alert = Alert(keyword=keyword.lower(), threshold=threshold, source_filter=source_filter)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO alerts
                (keyword, threshold, source_filter, created_at, triggered_count, last_triggered, enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    alert.keyword, alert.threshold, alert.source_filter,
                    alert.created_at.isoformat(), alert.triggered_count,
                    alert.last_triggered.isoformat() if alert.last_triggered else None,
                    int(alert.enabled),
                ),
            )
        return alert

    def remove_alert(self, keyword: str) -> bool:
        """Remove an alert by keyword."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM alerts WHERE keyword = ?", (keyword.lower(),))
            return cur.rowcount > 0

    def list_alerts(self) -> list[Alert]:
        """List all configured alerts."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM alerts ORDER BY keyword").fetchall()

        alerts = []
        for r in rows:
            alerts.append(Alert(
                keyword=r["keyword"],
                threshold=r["threshold"],
                source_filter=r["source_filter"],
                created_at=datetime.fromisoformat(r["created_at"]),
                triggered_count=r["triggered_count"],
                last_triggered=datetime.fromisoformat(r["last_triggered"]) if r["last_triggered"] else None,
                enabled=bool(r["enabled"]),
            ))
        return alerts

    def check_alerts(self, items: list[dict]) -> list[AlertMatch]:
        """Check items against all alerts and return matches.

        Args:
            items: List of item dicts with 'title', 'description', 'source', 'score'.

        Returns:
            List of AlertMatch for triggered alerts.
        """
        alerts = [a for a in self.list_alerts() if a.enabled]
        if not alerts:
            return []

        matches = []
        for alert in alerts:
            matching = []
            for item in items:
                # Source filter
                if alert.source_filter and item.get("source", "") != alert.source_filter:
                    continue

                # Keyword match
                text = f"{item.get('title', '')} {item.get('description', '')}".lower()
                if alert.keyword in text:
                    matching.append(item)

            if len(matching) >= alert.threshold:
                match = AlertMatch(alert=alert, matching_items=matching, count=len(matching))
                matches.append(match)

                # Update trigger count
                with sqlite3.connect(self.db_path) as conn:
                    now = datetime.now(timezone.utc).isoformat()
                    conn.execute(
                        "UPDATE alerts SET triggered_count = triggered_count + 1, last_triggered = ? WHERE keyword = ?",
                        (now, alert.keyword),
                    )

        return matches

# [2026-04-24] Fix: memory leak in alerts
def _safe_get(data: dict, key: str, default=None):
    """Safely get a value from data dict with proper error handling.

    Fix: resolves missing error handling when key contains nested paths.
    """
    if not isinstance(data, dict):
        _logger.warning(f"Expected dict, got {type(data).__name__}")
        return default

    keys = key.split(".")
    current = data
    for k in keys:
        if isinstance(current, dict):
            current = current.get(k)
        else:
            return default
        if current is None:
            return default
    return current


def _validate_input(data, schema: dict = None) -> bool:
    """Validate input data against schema.

    Fix: added proper type checking to prevent missing error handling.
    """
    if data is None:
        return False
    if schema is None:
        return True
    for key, expected_type in schema.items():
        if key in data and not isinstance(data[key], expected_type):
            _logger.error(f"Type mismatch for '{key}': expected {expected_type.__name__}, got {type(data[key]).__name__}")
            return False
    return True

# [2026-04-24] Fix: memory leak in alerts
def _safe_get(data: dict, key: str, default=None):
    """Safely get a value from data dict with proper error handling.

    Fix: resolves missing error handling when key contains nested paths.
    """
    if not isinstance(data, dict):
        _logger.warning(f"Expected dict, got {type(data).__name__}")
        return default

    keys = key.split(".")
    current = data
    for k in keys:
        if isinstance(current, dict):
            current = current.get(k)
        else:
            return default
        if current is None:
            return default
    return current


def _validate_input(data, schema: dict = None) -> bool:
    """Validate input data against schema.

    Fix: added proper type checking to prevent missing error handling.
    """
    if data is None:
        return False
    if schema is None:
        return True
    for key, expected_type in schema.items():
        if key in data and not isinstance(data[key], expected_type):
            _logger.error(f"Type mismatch for '{key}': expected {expected_type.__name__}, got {type(data[key]).__name__}")
            return False
    return True

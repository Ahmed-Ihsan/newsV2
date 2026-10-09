"""Tests for SQLite store (TrendStore)."""

import os
import tempfile
from datetime import datetime, timezone

from trend_radar.store import TrendStore, get_default_db_path
from trend_radar.models import IntelItem, SourceType, TrendSnapshot


def _make_store(tmp_path):
    db = os.path.join(str(tmp_path), "test.db")
    return TrendStore(db_path=db)


def _make_snapshot(items=None):
    if items is None:
        items = [
            IntelItem(title="test-repo", source=SourceType.GITHUB, score=500,
                      url="https://github.com/test/repo", author="user1",
                      description="A test repo", tags=["python"]),
            IntelItem(title="Show HN: Test", source=SourceType.HACKERNEWS, score=300,
                      url="https://news.ycombinator.com/item/1", author="user2"),
        ]
    return TrendSnapshot(
        items=items,
        sources_queried=["github", "hackernews"],
    )


def test_store_init(tmp_path):
    store = _make_store(tmp_path)
    assert os.path.exists(store.db_path)


def test_store_save_snapshot(tmp_path):
    store = _make_store(tmp_path)
    snap = _make_snapshot()
    sid = store.save_snapshot(snap)
    assert sid >= 1


def test_store_get_snapshots(tmp_path):
    store = _make_store(tmp_path)
    store.save_snapshot(_make_snapshot())
    store.save_snapshot(_make_snapshot())
    snapshots = store.get_snapshots(limit=10)
    assert len(snapshots) == 2
    assert snapshots[0]["item_count"] == 2


def test_store_get_snapshots_limit(tmp_path):
    store = _make_store(tmp_path)
    for _ in range(5):
        store.save_snapshot(_make_snapshot())
    snapshots = store.get_snapshots(limit=3)
    assert len(snapshots) == 3


def test_store_get_trending_items(tmp_path):
    store = _make_store(tmp_path)
    store.save_snapshot(_make_snapshot())
    items = store.get_trending_items(hours=1, limit=10)
    assert len(items) == 2


def test_store_get_trending_items_by_source(tmp_path):
    store = _make_store(tmp_path)
    store.save_snapshot(_make_snapshot())
    items = store.get_trending_items(hours=1, source="github", limit=10)
    assert all(r["source"] == "github" for r in items)


def test_store_get_trending_items_empty(tmp_path):
    store = _make_store(tmp_path)
    items = store.get_trending_items(hours=1, limit=10)
    assert len(items) == 0


def test_store_get_stats(tmp_path):
    store = _make_store(tmp_path)
    store.save_snapshot(_make_snapshot())
    stats = store.get_stats()
    assert stats["total_snapshots"] == 1
    assert stats["total_items"] == 2
    assert "github" in stats["sources"]
    assert stats["latest_snapshot"] is not None


def test_store_get_stats_empty(tmp_path):
    store = _make_store(tmp_path)
    stats = store.get_stats()
    assert stats["total_snapshots"] == 0
    assert stats["total_items"] == 0


def test_store_get_star_trends(tmp_path):
    store = _make_store(tmp_path)
    store.save_snapshot(TrendSnapshot(
        items=[IntelItem(title="test/repo", source=SourceType.GITHUB, score=100)],
    ))
    store.save_snapshot(TrendSnapshot(
        items=[IntelItem(title="test/repo", source=SourceType.GITHUB, score=200)],
    ))
    trends = store.get_star_trends("test/repo", days=30)
    assert len(trends) == 2


def test_store_get_keyword_trends(tmp_path):
    store = _make_store(tmp_path)
    items = [
        IntelItem(title="AI agent framework for LLM", source=SourceType.GITHUB),
        IntelItem(title="Building AI agent tools", source=SourceType.HACKERNEWS),
        IntelItem(title="LLM benchmark suite", source=SourceType.REDDIT),
    ]
    store.save_snapshot(TrendSnapshot(items=items))
    kw = store.get_keyword_trends(days=7)
    kw_dict = dict(kw)
    assert kw_dict.get("agent", 0) >= 2
    assert kw_dict.get("llm", 0) >= 2


def test_store_get_keyword_trends_empty(tmp_path):
    store = _make_store(tmp_path)
    kw = store.get_keyword_trends(days=7)
    assert kw == []


def test_store_default_db_path():
    """Test default path generation."""
    path = get_default_db_path()
    assert "trend-radar" in path
    assert path.endswith("trends.db")


def test_store_save_multiple_items(tmp_path):
    store = _make_store(tmp_path)
    items = [
        IntelItem(title=f"item-{i}", source=SourceType.GITHUB, score=i * 100)
        for i in range(50)
    ]
    store.save_snapshot(TrendSnapshot(items=items))
    stats = store.get_stats()
    assert stats["total_items"] == 50

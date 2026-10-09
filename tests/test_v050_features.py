"""Tests for concurrent fetching, diff, top, health, and topic filtering."""

import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from trend_radar.core import TrendRadar
from trend_radar.models import IntelItem, SourceType, TrendSnapshot


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temp directory for db/cache."""
    return str(tmp_path)


@pytest.fixture
def radar(tmp_dir):
    """Create a TrendRadar with temp storage."""
    db_path = str(Path(tmp_dir) / "test.db")
    config_path = str(Path(tmp_dir) / "config.yaml")
    return TrendRadar(db_path=db_path, config_path=config_path, use_cache=False)


def _make_item(title, source="github", score=100, url="http://x.com", desc="test"):
    """Helper to create an IntelItem."""
    return IntelItem(
        title=title,
        source=SourceType(source),
        url=url,
        description=desc,
        score=score,
        author="testuser",
    )


def _save_snapshot_with_items(radar, items, sources=None):
    """Save a snapshot with given items."""
    snapshot = TrendSnapshot(
        items=items,
        sources_queried=sources or list(set(i.source.value for i in items)),
    )
    return radar.store.save_snapshot(snapshot)


class TestConcurrentFetch:
    """Test concurrent source fetching."""

    def test_concurrent_returns_same_as_sequential(self, radar):
        """Concurrent fetch should return similar structure to sequential."""
        mock_items = [_make_item("test-repo", score=500)]

        for name, source in radar.sources.items():
            source.fetch = MagicMock(return_value=mock_items)

        result_seq = radar.collect(limit=5, parallel=False, save=False)
        result_con = radar.collect(limit=5, parallel=True, save=False)

        assert result_con.item_count == result_seq.item_count
        assert set(result_con.sources_queried) == set(result_seq.sources_queried)

    def test_concurrent_with_single_source(self, radar):
        """Concurrent with single source should still work."""
        radar.sources = {"github": radar.sources["github"]}
        radar.sources["github"].fetch = MagicMock(return_value=[_make_item("r1")])

        result = radar.collect(limit=5, parallel=True, save=False)
        assert result.item_count == 1

    def test_concurrent_error_handling(self, radar):
        """Errors in one source shouldn't affect others."""
        radar.sources["github"].fetch = MagicMock(return_value=[_make_item("r1")])
        radar.sources["hackernews"].fetch = MagicMock(side_effect=Exception("timeout"))

        result = radar.collect(limit=5, parallel=True, save=False)
        assert result.item_count >= 1
        assert any("hackernews" in e for e in result.errors)

    def test_sequential_fetch(self, radar):
        """Sequential fetch should work."""
        for name, source in radar.sources.items():
            source.fetch = MagicMock(return_value=[_make_item(f"item-{name}")])

        result = radar.collect(limit=5, parallel=False, save=False)
        assert result.item_count == len(radar.sources)

    def test_max_workers_parameter(self, radar):
        """max_workers parameter should be accepted."""
        for name, source in radar.sources.items():
            source.fetch = MagicMock(return_value=[_make_item(f"item-{name}")])

        result = radar.collect(limit=5, parallel=True, max_workers=2, save=False)
        assert result.item_count == len(radar.sources)


class TestDiffSnapshots:
    """Test snapshot diff functionality."""

    def test_diff_with_no_history(self, radar):
        """Diff with no history should return empty."""
        result = radar.diff_snapshots()
        assert result["rising"] == []
        assert result["falling"] == []
        assert result["new"] == []
        assert result["gone"] == []

    def test_diff_with_one_snapshot(self, radar):
        """Diff with only one snapshot should return empty."""
        _save_snapshot_with_items(radar, [_make_item("repo1", score=100)])
        result = radar.diff_snapshots()
        assert result["rising"] == []
        assert result["falling"] == []

    def test_diff_detects_rising(self, radar):
        """Diff should detect items with increasing scores."""
        _save_snapshot_with_items(radar, [_make_item("repo1", score=100)])
        _save_snapshot_with_items(radar, [_make_item("repo1", score=200)])

        result = radar.diff_snapshots()
        assert len(result["rising"]) == 1
        assert result["rising"][0]["score_delta"] == 100

    def test_diff_detects_falling(self, radar):
        """Diff should detect items with decreasing scores."""
        _save_snapshot_with_items(radar, [_make_item("repo1", score=200)])
        _save_snapshot_with_items(radar, [_make_item("repo1", score=100)])

        result = radar.diff_snapshots()
        assert len(result["falling"]) == 1
        assert result["falling"][0]["score_delta"] == -100

    def test_diff_detects_new_items(self, radar):
        """Diff should detect new items not in previous snapshot."""
        _save_snapshot_with_items(radar, [_make_item("repo1", score=100)])
        _save_snapshot_with_items(radar, [
            _make_item("repo1", score=100),
            _make_item("repo2", score=50),
        ])

        result = radar.diff_snapshots()
        assert len(result["new"]) == 1
        assert result["new"][0]["title"] == "repo2"

    def test_diff_detects_gone_items(self, radar):
        """Diff should detect items that disappeared."""
        _save_snapshot_with_items(radar, [
            _make_item("repo1", score=100),
            _make_item("repo2", score=50),
        ])
        _save_snapshot_with_items(radar, [_make_item("repo1", score=100)])

        result = radar.diff_snapshots()
        assert len(result["gone"]) == 1

    def test_diff_case_insensitive(self, radar):
        """Diff should match titles case-insensitively."""
        _save_snapshot_with_items(radar, [_make_item("My Repo", score=100)])
        _save_snapshot_with_items(radar, [_make_item("my repo", score=200)])

        result = radar.diff_snapshots()
        assert len(result["rising"]) == 1

    def test_diff_counts(self, radar):
        """Diff should include correct item counts."""
        _save_snapshot_with_items(radar, [_make_item("r1", score=10)])
        _save_snapshot_with_items(radar, [_make_item("r1", score=20), _make_item("r2", score=30)])

        result = radar.diff_snapshots()
        assert result["previous_count"] == 1
        assert result["current_count"] == 2


class TestGetTopItems:
    """Test top items retrieval."""

    def test_top_items_basic(self, radar):
        """Should return items sorted by score."""
        _save_snapshot_with_items(radar, [
            _make_item("low", score=10),
            _make_item("high", score=100),
            _make_item("mid", score=50),
        ])

        items = radar.get_top_items(limit=3)
        assert len(items) == 3
        assert items[0].title == "high"
        assert items[1].title == "mid"
        assert items[2].title == "low"

    def test_top_items_with_source_filter(self, radar):
        """Should filter by source."""
        _save_snapshot_with_items(radar, [
            _make_item("gh-item", source="github", score=100),
            _make_item("hn-item", source="hackernews", score=200),
        ])

        items = radar.get_top_items(limit=10, source="github")
        assert all(i.source == SourceType.GITHUB for i in items)

    def test_top_items_with_topic_filter(self, radar):
        """Should filter by topic."""
        _save_snapshot_with_items(radar, [
            _make_item("AI agent framework", score=100, desc="machine learning"),
            _make_item("React component library", score=200, desc="frontend UI"),
        ])

        items = radar.get_top_items(limit=10, topic="ai")
        assert len(items) == 1
        assert items[0].title == "AI agent framework"

    def test_top_items_topic_web(self, radar):
        """Topic filter should work for 'web' topic."""
        _save_snapshot_with_items(radar, [
            _make_item("React hooks", score=50, desc="frontend"),
            _make_item("Rust compiler", score=80, desc="systems programming"),
        ])

        items = radar.get_top_items(limit=10, topic="web")
        assert len(items) == 1
        assert "React" in items[0].title

    def test_top_items_unknown_topic(self, radar):
        """Unknown topic should not filter."""
        _save_snapshot_with_items(radar, [_make_item("any item", score=100)])

        items = radar.get_top_items(limit=10, topic="nonexistent")
        assert len(items) == 1

    def test_top_items_limit(self, radar):
        """Should respect limit."""
        _save_snapshot_with_items(radar, [_make_item(f"item-{i}", score=i) for i in range(50)])

        items = radar.get_top_items(limit=5)
        assert len(items) == 5


class TestCheckHealth:
    """Test source health checking."""

    def test_health_all_ok(self, radar):
        """All sources returning items should show ok."""
        for source in radar.sources.values():
            source.fetch = MagicMock(return_value=[_make_item("test")])

        results = radar.check_health()
        assert all(r["status"] == "ok" for r in results.values())
        assert all(r["latency_ms"] >= 0 for r in results.values())

    def test_health_source_error(self, radar):
        """Source errors should be reported."""
        radar.sources["github"].fetch = MagicMock(side_effect=Exception("API error"))
        for name, source in radar.sources.items():
            if name != "github":
                source.fetch = MagicMock(return_value=[_make_item("test")])

        results = radar.check_health()
        assert results["github"]["status"] == "error"
        assert "API error" in results["github"]["error"]

    def test_health_empty_source(self, radar):
        """Source returning empty should show 'empty'."""
        radar.sources["github"].fetch = MagicMock(return_value=[])
        for name, source in radar.sources.items():
            if name != "github":
                source.fetch = MagicMock(return_value=[_make_item("test")])

        results = radar.check_health()
        assert results["github"]["status"] == "empty"

    def test_health_returns_all_sources(self, radar):
        """Should return health info for all sources."""
        for source in radar.sources.values():
            source.fetch = MagicMock(return_value=[_make_item("test")])

        results = radar.check_health()
        assert len(results) == len(radar.sources)

    def test_health_latency_ms(self, radar):
        """Latency should be a reasonable number."""
        for source in radar.sources.values():
            source.fetch = MagicMock(return_value=[_make_item("test")])

        results = radar.check_health()
        for r in results.values():
            assert isinstance(r["latency_ms"], int)
            assert r["latency_ms"] >= 0


class TestTopicFiltering:
    """Test topic keyword matching."""

    def test_topic_ai_matches(self, radar):
        """AI topic should match AI-related items."""
        item = _make_item("GPT-4 agent framework", desc="LLM based", score=100)
        assert radar._matches_topic(item, "ai")

    def test_topic_web_matches(self, radar):
        """Web topic should match web-related items."""
        item = _make_item("React component", desc="frontend UI", score=100)
        assert radar._matches_topic(item, "web")

    def test_topic_security_matches(self, radar):
        """Security topic should match security items."""
        item = _make_item("CVE-2024-1234", desc="vulnerability in auth", score=100)
        assert radar._matches_topic(item, "security")

    def test_topic_devops_matches(self, radar):
        """DevOps topic should match DevOps items."""
        item = _make_item("Kubernetes deployment", desc="docker k8s", score=100)
        assert radar._matches_topic(item, "devops")

    def test_topic_mobile_matches(self, radar):
        """Mobile topic should match mobile items."""
        item = _make_item("Flutter app", desc="iOS android", score=100)
        assert radar._matches_topic(item, "mobile")

    def test_topic_data_matches(self, radar):
        """Data topic should match data items."""
        item = _make_item("PostgreSQL optimizer", desc="database SQL", score=100)
        assert radar._matches_topic(item, "data")

    def test_topic_lang_matches(self, radar):
        """Lang topic should match programming language items."""
        item = _make_item("Rust borrow checker", desc="compiler", score=100)
        assert radar._matches_topic(item, "lang")

    def test_topic_no_match(self, radar):
        """Unrelated items should not match."""
        item = _make_item("Random recipe", desc="cooking food", score=100)
        assert not radar._matches_topic(item, "ai")

    def test_topic_unknown_passes(self, radar):
        """Unknown topics should pass all items."""
        item = _make_item("Anything", desc="anything", score=100)
        assert radar._matches_topic(item, "nonexistent_topic")


class TestStoreSnapshotItems:
    """Test the new get_snapshot_items method."""

    def test_get_snapshot_items(self, radar):
        """Should return items for a specific snapshot."""
        items = [_make_item(f"item-{i}", score=i * 10) for i in range(5)]
        sid = _save_snapshot_with_items(radar, items)

        result = radar.store.get_snapshot_items(sid)
        assert len(result) == 5
        assert all("title" in r for r in result)

    def test_get_snapshot_items_empty(self, radar):
        """Should return empty for non-existent snapshot."""
        result = radar.store.get_snapshot_items(9999)
        assert result == []

    def test_get_snapshot_items_fields(self, radar):
        """Returned items should have all expected fields."""
        sid = _save_snapshot_with_items(radar, [_make_item("test", score=42)])

        result = radar.store.get_snapshot_items(sid)
        assert len(result) == 1
        item = result[0]
        assert item["title"] == "test"
        assert item["score"] == 42
        assert "source" in item
        assert "url" in item
        assert "description" in item


class TestConcurrentCollectSave:
    """Test that concurrent fetch properly saves to store."""

    def test_concurrent_saves_to_store(self, radar, tmp_dir):
        """Concurrent fetch should save snapshot to database."""
        for source in radar.sources.values():
            source.fetch = MagicMock(return_value=[_make_item("saved-item")])

        result = radar.collect(limit=5, parallel=True, save=True)
        assert result.item_count > 0

        stats = radar.store.get_stats()
        assert stats["total_snapshots"] >= 1
        assert stats["total_items"] >= 1

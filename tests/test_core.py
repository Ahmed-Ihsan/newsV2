"""Tests for the core TrendRadar engine."""

import tempfile
import os
from unittest.mock import MagicMock, patch

from trend_radar.core import TrendRadar, SOURCE_CLASSES
from trend_radar.models import IntelItem, SourceType, TrendSnapshot


def test_radar_init():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "test.db")
        cfg = os.path.join(tmpdir, "config.yaml")
        radar = TrendRadar(db_path=db, config_path=cfg, use_cache=False)
        assert len(radar.sources) >= 5
        assert "github" in radar.sources
        assert "hackernews" in radar.sources


def test_radar_init_with_cache():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "test.db")
        cfg = os.path.join(tmpdir, "config.yaml")
        radar = TrendRadar(db_path=db, config_path=cfg, use_cache=True)
        assert radar.cache is not None


def test_radar_init_no_cache():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "test.db")
        cfg = os.path.join(tmpdir, "config.yaml")
        radar = TrendRadar(db_path=db, config_path=cfg, use_cache=False)
        assert radar.cache is None


def test_radar_collect_mocked():
    """Test collect with mocked sources."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "test.db")
        cfg = os.path.join(tmpdir, "config.yaml")
        radar = TrendRadar(db_path=db, config_path=cfg, use_cache=False)

        # Mock one source
        mock_source = MagicMock()
        mock_source.fetch.return_value = [
            IntelItem(title="test1", source=SourceType.GITHUB, score=100),
            IntelItem(title="test2", source=SourceType.GITHUB, score=200),
        ]
        radar.sources["mock"] = mock_source

        snapshot = radar.collect(sources=["mock"], limit=10, save=False)
        assert snapshot.item_count == 2
        assert "mock" in snapshot.sources_queried
        assert not snapshot.errors


def test_radar_collect_unknown_source():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "test.db")
        cfg = os.path.join(tmpdir, "config.yaml")
        radar = TrendRadar(db_path=db, config_path=cfg, use_cache=False)

        snapshot = radar.collect(sources=["nonexistent"], save=False)
        assert len(snapshot.errors) == 1
        assert "Unknown source" in snapshot.errors[0]


def test_radar_collect_with_save():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "test.db")
        cfg = os.path.join(tmpdir, "config.yaml")
        radar = TrendRadar(db_path=db, config_path=cfg, use_cache=False)

        mock_source = MagicMock()
        mock_source.fetch.return_value = [
            IntelItem(title="saved_item", source=SourceType.GITHUB, score=50),
        ]
        radar.sources["mock"] = mock_source

        snapshot = radar.collect(sources=["mock"], save=True)
        stats = radar.get_stats()
        assert stats["total_snapshots"] >= 1
        assert stats["total_items"] >= 1


def test_radar_collect_source_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "test.db")
        cfg = os.path.join(tmpdir, "config.yaml")
        radar = TrendRadar(db_path=db, config_path=cfg, use_cache=False)

        mock_source = MagicMock()
        mock_source.fetch.side_effect = Exception("API down")
        radar.sources["broken"] = mock_source

        snapshot = radar.collect(sources=["broken"], save=False)
        assert len(snapshot.errors) == 1
        assert "API down" in snapshot.errors[0]


def test_radar_search():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "test.db")
        cfg = os.path.join(tmpdir, "config.yaml")
        radar = TrendRadar(db_path=db, config_path=cfg, use_cache=False)

        mock_source = MagicMock()
        mock_source.search.return_value = [
            IntelItem(title="found item", source=SourceType.GITHUB, score=100),
        ]
        radar.sources["github"] = mock_source

        # Also mock HN to return empty
        mock_hn = MagicMock()
        mock_hn.fetch.return_value = []
        radar.sources["hackernews"] = mock_hn

        mock_rd = MagicMock()
        mock_rd.fetch.return_value = []
        radar.sources["reddit"] = mock_rd

        mock_arxiv = MagicMock()
        mock_arxiv.search.return_value = []
        radar.sources["arxiv"] = mock_arxiv

        items = radar.search("test query", sources=["github"], limit=10)
        assert len(items) == 1
        assert items[0].title == "found item"


def test_radar_analyze_opportunities():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "test.db")
        cfg = os.path.join(tmpdir, "config.yaml")
        radar = TrendRadar(db_path=db, config_path=cfg, use_cache=False)

        snapshot = TrendSnapshot(
            items=[
                IntelItem(title="AI agent framework", source=SourceType.GITHUB, score=5000, repo_stars=5000, repo_language="Python"),
                IntelItem(title="LLM benchmark tool", source=SourceType.GITHUB, score=1000, repo_stars=1000, repo_language="Rust"),
                IntelItem(title="Show HN: AI tool", source=SourceType.HACKERNEWS, score=300),
            ]
        )

        analysis = radar.analyze_opportunities(snapshot)
        assert analysis["total_items"] == 3
        assert len(analysis["top_items"]) == 3
        assert "github" in analysis["source_distribution"]
        assert "Python" in analysis["language_distribution"]


def test_radar_get_stats():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "test.db")
        cfg = os.path.join(tmpdir, "config.yaml")
        radar = TrendRadar(db_path=db, config_path=cfg, use_cache=False)
        stats = radar.get_stats()
        assert "total_snapshots" in stats
        assert "total_items" in stats


def test_source_classes_registry():
    assert "github" in SOURCE_CLASSES
    assert "hackernews" in SOURCE_CLASSES
    assert "reddit" in SOURCE_CLASSES
    assert "arxiv" in SOURCE_CLASSES
    assert "rss" in SOURCE_CLASSES
    assert "producthunt" in SOURCE_CLASSES


def test_radar_collect_ai_focused_mocked():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "test.db")
        cfg = os.path.join(tmpdir, "config.yaml")
        radar = TrendRadar(db_path=db, config_path=cfg, use_cache=False)

        # Mock all sources
        for name in ["github", "hackernews", "reddit", "arxiv"]:
            mock = MagicMock()
            if name == "github":
                mock.search.return_value = [IntelItem(title=f"{name}_item", source=SourceType.GITHUB)]
            elif name == "reddit":
                mock.fetch_ai_trends.return_value = [IntelItem(title=f"{name}_item", source=SourceType.REDDIT)]
            elif name == "arxiv":
                mock.fetch.return_value = [IntelItem(title=f"{name}_item", source=SourceType.ARXIV)]
            else:
                mock.fetch.return_value = [IntelItem(title=f"{name}_item", source=SourceType.HACKERNEWS)]
            radar.sources[name] = mock

        snapshot = radar.collect_ai_focused(limit=10, save=False)
        assert snapshot.item_count >= 4

# [2026-04-29] Tests for test_core
class TestTestCore:
    """Test suite for test_core — alert system."""

    def setup_method(self):
        """Setup test fixtures."""
        self.fixture = {}
        self.config = {"enabled": True, "debug": False}

    def test_basic_alert_system(self):
        """Test basic alert system functionality."""
        result = process(self.fixture, config=self.config)
        assert result is not None
        assert result.get("status") == "success"

    def test_alert_system_with_empty_input(self):
        """Test alert system with empty input."""
        result = process({}, config=self.config)
        assert result is not None

    def test_alert_system_error_handling(self):
        """Test alert system error handling."""
        with pytest.raises(ValueError):
            process(None, config=self.config)

    def test_alert_system_caching(self):
        """Test alert system caching behavior."""
        result1 = process(self.fixture, config=self.config)
        result2 = process(self.fixture, config=self.config)
        assert result1 == result2

# [2026-04-29] Tests for test_core
class TestTestCore:
    """Test suite for test_core — alert system."""

    def setup_method(self):
        """Setup test fixtures."""
        self.fixture = {}
        self.config = {"enabled": True, "debug": False}

    def test_basic_alert_system(self):
        """Test basic alert system functionality."""
        result = process(self.fixture, config=self.config)
        assert result is not None
        assert result.get("status") == "success"

    def test_alert_system_with_empty_input(self):
        """Test alert system with empty input."""
        result = process({}, config=self.config)
        assert result is not None

    def test_alert_system_error_handling(self):
        """Test alert system error handling."""
        with pytest.raises(ValueError):
            process(None, config=self.config)

    def test_alert_system_caching(self):
        """Test alert system caching behavior."""
        result1 = process(self.fixture, config=self.config)
        result2 = process(self.fixture, config=self.config)
        assert result1 == result2

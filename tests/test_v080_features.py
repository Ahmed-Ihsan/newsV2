"""Tests for v0.8.0 features — radar chart, bookmarks, plugins, rate limiter."""

import json
import os
import sqlite3
import tempfile
import time
import threading

import pytest


# ============================================================
# Radar Chart Tests
# ============================================================

class TestClassifyItem:
    """Test topic classification of IntelItem."""

    def test_classify_ai(self):
        from trend_radar.models import IntelItem, SourceType
        from trend_radar.radar_chart import classify_item

        item = IntelItem(
            title="GPT-5 released with new transformer architecture",
            source=SourceType.HACKERNEWS,
        )
        assert classify_item(item) == "ai"

    def test_classify_web(self):
        from trend_radar.models import IntelItem, SourceType
        from trend_radar.radar_chart import classify_item

        item = IntelItem(
            title="React 20 with new Svelte-like reactivity",
            source=SourceType.GITHUB,
        )
        assert classify_item(item) == "web"

    def test_classify_security(self):
        from trend_radar.models import IntelItem, SourceType
        from trend_radar.radar_chart import classify_item

        item = IntelItem(
            title="Critical CVE in OpenSSL allows remote exploit",
            source=SourceType.REDDIT,
        )
        assert classify_item(item) == "security"

    def test_classify_devops(self):
        from trend_radar.models import IntelItem, SourceType
        from trend_radar.radar_chart import classify_item

        item = IntelItem(
            title="Kubernetes 2.0 with native Docker support",
            source=SourceType.HACKERNEWS,
        )
        assert classify_item(item) == "devops"

    def test_classify_lang(self):
        from trend_radar.models import IntelItem, SourceType
        from trend_radar.radar_chart import classify_item

        item = IntelItem(
            title="Rust compiler now 50% faster with new parser",
            source=SourceType.GITHUB,
        )
        assert classify_item(item) == "lang"

    def test_classify_data(self):
        from trend_radar.models import IntelItem, SourceType
        from trend_radar.radar_chart import classify_item

        item = IntelItem(
            title="Postgres 18 with streaming analytics pipeline",
            source=SourceType.RSS,
        )
        assert classify_item(item) == "data"

    def test_classify_mobile(self):
        from trend_radar.models import IntelItem, SourceType
        from trend_radar.radar_chart import classify_item

        item = IntelItem(
            title="Flutter 5.0 for iOS and Android development",
            source=SourceType.GITHUB,
        )
        assert classify_item(item) == "mobile"

    def test_classify_other(self):
        from trend_radar.models import IntelItem, SourceType
        from trend_radar.radar_chart import classify_item

        item = IntelItem(
            title="How to organize your desk for productivity",
            source=SourceType.REDDIT,
        )
        assert classify_item(item) == "other"


class TestTopicDistribution:
    """Test topic distribution computation."""

    def test_compute_distribution(self):
        from trend_radar.models import IntelItem, SourceType
        from trend_radar.radar_chart import compute_topic_distribution

        items = [
            IntelItem(title="LLM agent framework", source=SourceType.GITHUB),
            IntelItem(title="React tutorial", source=SourceType.HACKERNEWS),
            IntelItem(title="Docker best practices", source=SourceType.REDDIT),
            IntelItem(title="Random blog post", source=SourceType.RSS),
        ]
        dist = compute_topic_distribution(items)
        assert dist["ai"] == 1
        assert dist["web"] == 1
        assert dist["devops"] == 1
        assert dist["other"] == 1

    def test_empty_items(self):
        from trend_radar.radar_chart import compute_topic_distribution
        dist = compute_topic_distribution([])
        assert all(v == 0 for v in dist.values())


class TestRadarChartRendering:
    """Test radar chart rendering functions."""

    def test_draw_bar_chart(self):
        from trend_radar.radar_chart import _draw_bar_chart
        dist = {"ai": 10, "web": 5, "security": 3, "other": 1}
        lines = _draw_bar_chart(dist, width=50)
        assert len(lines) > 0
        assert any("AI" in line for line in lines)

    def test_draw_radar_ascii(self):
        from trend_radar.radar_chart import _draw_radar_ascii
        dist = {"ai": 10, "web": 5, "security": 3, "devops": 7, "data": 2}
        lines = _draw_radar_ascii(dist, width=50, height=20)
        assert len(lines) > 0
        assert all(isinstance(line, str) for line in lines)

    def test_render_radar_chart(self):
        from rich.console import Console
        from trend_radar.models import IntelItem, SourceType
        from trend_radar.radar_chart import render_radar_chart
        import io

        console = Console(file=io.StringIO(), width=80)
        items = [
            IntelItem(title="AI model", source=SourceType.GITHUB),
            IntelItem(title="React app", source=SourceType.HACKERNEWS),
            IntelItem(title="Docker guide", source=SourceType.REDDIT),
        ]
        render_radar_chart(console, items)
        output = console.file.getvalue()
        assert "Topic Radar" in output

    def test_render_radar_empty(self):
        from rich.console import Console
        from trend_radar.radar_chart import render_radar_chart
        import io

        console = Console(file=io.StringIO(), width=80)
        render_radar_chart(console, [])
        output = console.file.getvalue()
        assert "No items" in output

    def test_render_topic_breakdown(self):
        from rich.console import Console
        from trend_radar.models import IntelItem, SourceType
        from trend_radar.radar_chart import render_topic_breakdown
        import io

        console = Console(file=io.StringIO(), width=80)
        items = [
            IntelItem(title="AI model", source=SourceType.GITHUB, score=100),
            IntelItem(title="React app", source=SourceType.HACKERNEWS, score=50),
        ]
        render_topic_breakdown(console, items)
        output = console.file.getvalue()
        assert "Topic Breakdown" in output


# ============================================================
# Bookmark Tests
# ============================================================

class TestBookmarkStore:
    """Test bookmark CRUD operations."""

    @pytest.fixture
    def store(self, tmp_path):
        from trend_radar.bookmarks import BookmarkStore
        db = str(tmp_path / "test.db")
        return BookmarkStore(db_path=db)

    @pytest.fixture
    def sample_item(self):
        from trend_radar.models import IntelItem, SourceType
        return IntelItem(
            title="Awesome Rust Project",
            source=SourceType.GITHUB,
            url="https://github.com/test/repo",
            description="A cool Rust project",
            score=500,
            author="testuser",
            tags=["rust", "cli"],
        )

    def test_add_and_get(self, store, sample_item):
        bid = store.add(sample_item)
        assert bid > 0
        bm = store.get(bid)
        assert bm is not None
        assert bm["title"] == "Awesome Rust Project"
        assert bm["source"] == "github"
        assert bm["score"] == 500

    def test_add_with_notes(self, store, sample_item):
        bid = store.add(sample_item, notes="Check this later", starred=True)
        bm = store.get(bid)
        assert bm["notes"] == "Check this later"
        assert bm["starred"] == 1

    def test_list_all(self, store, sample_item):
        from trend_radar.models import IntelItem, SourceType
        store.add(sample_item)
        store.add(IntelItem(title="Another item", source=SourceType.REDDIT))
        bookmarks = store.list_all()
        assert len(bookmarks) == 2

    def test_list_filter_source(self, store, sample_item):
        from trend_radar.models import IntelItem, SourceType
        store.add(sample_item)
        store.add(IntelItem(title="Reddit post", source=SourceType.REDDIT))
        gh = store.list_all(source="github")
        assert len(gh) == 1
        assert gh[0]["source"] == "github"

    def test_list_starred_only(self, store, sample_item):
        from trend_radar.models import IntelItem, SourceType
        store.add(sample_item, starred=True)
        store.add(IntelItem(title="Normal", source=SourceType.REDDIT))
        starred = store.list_all(starred_only=True)
        assert len(starred) == 1

    def test_search(self, store, sample_item):
        store.add(sample_item)
        results = store.search("Rust")
        assert len(results) == 1
        results = store.search("nonexistent")
        assert len(results) == 0

    def test_remove(self, store, sample_item):
        bid = store.add(sample_item)
        assert store.remove(bid) is True
        assert store.get(bid) is None
        assert store.remove(999) is False

    def test_toggle_star(self, store, sample_item):
        bid = store.add(sample_item)
        assert store.toggle_star(bid) is True
        assert store.get(bid)["starred"] == 1
        assert store.toggle_star(bid) is False
        assert store.get(bid)["starred"] == 0

    def test_update_notes(self, store, sample_item):
        bid = store.add(sample_item)
        assert store.update_notes(bid, "New notes") is True
        assert store.get(bid)["notes"] == "New notes"

    def test_count(self, store, sample_item):
        assert store.count() == 0
        store.add(sample_item)
        assert store.count() == 1

    def test_export_json(self, store, sample_item):
        store.add(sample_item)
        data = json.loads(store.export_json())
        assert len(data) == 1
        assert data[0]["title"] == "Awesome Rust Project"

    def test_to_intel_items(self, store, sample_item):
        bid = store.add(sample_item)
        bookmarks = store.list_all()
        items = store.to_intel_items(bookmarks)
        assert len(items) == 1
        assert items[0].title == "Awesome Rust Project"
        assert items[0].source.value == "github"

    def test_empty_search(self, store):
        results = store.search("test")
        assert results == []


# ============================================================
# Plugin Tests
# ============================================================

class TestPluginManager:
    """Test plugin registration and loading."""

    @pytest.fixture
    def manager(self, tmp_path):
        from trend_radar.plugins import PluginManager
        return PluginManager(plugin_dirs=[str(tmp_path / "plugins")])

    def test_register_plugin(self, manager):
        from trend_radar.sources import DataSource
        from trend_radar.models import IntelItem, SourceType

        class TestSource(DataSource):
            def fetch(self, limit=25, **kwargs):
                return [IntelItem(title="Test", source=SourceType.RSS)]

        manager.register("test", TestSource)
        assert "test" in manager
        assert len(manager) == 1

    def test_register_invalid(self, manager):
        with pytest.raises(TypeError):
            manager.register("bad", str)  # Not a DataSource

    def test_get_source(self, manager):
        from trend_radar.sources import DataSource
        from trend_radar.models import IntelItem, SourceType

        class TestSource(DataSource):
            def fetch(self, limit=25, **kwargs):
                return [IntelItem(title="Test", source=SourceType.RSS)]

        manager.register("test", TestSource)
        source = manager.get_source("test")
        assert source is not None
        items = source.fetch(limit=5)
        assert len(items) == 1

    def test_get_source_caching(self, manager):
        from trend_radar.sources import DataSource
        from trend_radar.models import IntelItem, SourceType

        class TestSource(DataSource):
            def fetch(self, limit=25, **kwargs):
                return []

        manager.register("test", TestSource)
        s1 = manager.get_source("test")
        s2 = manager.get_source("test")
        assert s1 is s2  # Same instance

    def test_get_unknown(self, manager):
        assert manager.get_source("nonexistent") is None

    def test_unregister(self, manager):
        from trend_radar.sources import DataSource
        from trend_radar.models import IntelItem, SourceType

        class TestSource(DataSource):
            def fetch(self, limit=25, **kwargs):
                return []

        manager.register("test", TestSource)
        assert manager.unregister("test") is True
        assert "test" not in manager
        assert manager.unregister("nonexistent") is False

    def test_list_plugins(self, manager):
        from trend_radar.sources import DataSource
        from trend_radar.models import IntelItem, SourceType

        class TestSource(DataSource):
            """A test source."""
            def fetch(self, limit=25, **kwargs):
                return []

        manager.register("test", TestSource)
        plugins = manager.list_plugins()
        assert "test" in plugins
        assert plugins["test"]["class"] == "TestSource"
        assert plugins["test"]["doc"] == "A test source."

    def test_source_names(self, manager):
        from trend_radar.sources import DataSource
        from trend_radar.models import IntelItem, SourceType

        class A(DataSource):
            def fetch(self, limit=25, **kwargs):
                return []

        class B(DataSource):
            def fetch(self, limit=25, **kwargs):
                return []

        manager.register("a", A)
        manager.register("b", B)
        assert set(manager.source_names) == {"a", "b"}

    def test_load_from_file(self, tmp_path):
        from trend_radar.plugins import PluginManager

        # Create a plugin file
        plugin_code = '''
from trend_radar.sources import DataSource
from trend_radar.models import IntelItem, SourceType

class CustomSource(DataSource):
    """Custom test source."""
    def fetch(self, limit=25, **kwargs):
        return [IntelItem(title="Custom Item", source=SourceType.RSS)]
'''
        plugin_file = tmp_path / "custom_source.py"
        plugin_file.write_text(plugin_code)

        manager = PluginManager(plugin_dirs=[str(tmp_path / "plugins")])
        # Test load_from_directory won't load from wrong dir
        loaded = manager.load_from_directory()
        assert len(loaded) == 0

    def test_load_from_directory(self, tmp_path):
        from trend_radar.plugins import PluginManager

        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        plugin_code = '''
from trend_radar.sources import DataSource
from trend_radar.models import IntelItem, SourceType

class CustomSource(DataSource):
    def fetch(self, limit=25, **kwargs):
        return [IntelItem(title="Custom", source=SourceType.RSS)]
'''
        (plugin_dir / "custom.py").write_text(plugin_code)

        manager = PluginManager(plugin_dirs=[str(plugin_dir)])
        loaded = manager.load_from_directory()
        assert "custom" in loaded
        source = manager.get_source("custom")
        assert source is not None

    def test_load_from_directory_ignores_init(self, tmp_path):
        from trend_radar.plugins import PluginManager

        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("")

        manager = PluginManager(plugin_dirs=[str(plugin_dir)])
        loaded = manager.load_from_directory()
        assert len(loaded) == 0


# ============================================================
# Rate Limiter Tests
# ============================================================

class TestTokenBucket:
    """Test token bucket rate limiter."""

    def test_acquire_immediate(self):
        from trend_radar.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(capacity=5, refill_rate=10.0)
        assert limiter.acquire(timeout=0) is True

    def test_exhaust_bucket(self):
        from trend_radar.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(capacity=3, refill_rate=100.0)
        # Consume all tokens
        for _ in range(3):
            assert limiter.acquire(timeout=0) is True
        # Should be empty now
        assert limiter.acquire(timeout=0) is False

    def test_refill(self):
        from trend_radar.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(capacity=2, refill_rate=100.0)
        # Exhaust
        limiter.acquire(timeout=0)
        limiter.acquire(timeout=0)
        assert limiter.acquire(timeout=0) is False
        # Wait for refill
        time.sleep(0.05)
        assert limiter.acquire(timeout=0) is True

    def test_try_acquire(self):
        from trend_radar.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(capacity=2, refill_rate=1.0)
        assert limiter.try_acquire() is True
        assert limiter.try_acquire() is True
        assert limiter.try_acquire() is False

    def test_available_tokens(self):
        from trend_radar.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(capacity=5, refill_rate=1.0)
        assert limiter.available_tokens == 5.0
        limiter.acquire(timeout=0)
        assert limiter.available_tokens < 5.0

    def test_repr(self):
        from trend_radar.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(capacity=10, refill_rate=2.0)
        r = repr(limiter)
        assert "TokenBucketRateLimiter" in r
        assert "10" in r

    def test_acquire_with_timeout(self):
        from trend_radar.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(capacity=1, refill_rate=10.0)
        limiter.acquire(timeout=0)  # Consume the token
        # Should succeed after brief wait
        start = time.monotonic()
        result = limiter.acquire(timeout=0.5)
        elapsed = time.monotonic() - start
        assert result is True
        assert elapsed < 0.5

    def test_acquire_timeout_expires(self):
        from trend_radar.rate_limiter import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(capacity=1, refill_rate=0.1)
        limiter.acquire(timeout=0)  # Consume
        # Should fail quickly
        result = limiter.acquire(timeout=0.05)
        assert result is False


class TestRateLimiterRegistry:
    """Test rate limiter registry."""

    def test_default_sources(self):
        from trend_radar.rate_limiter import RateLimiterRegistry
        registry = RateLimiterRegistry()
        assert "github" in registry
        assert "hackernews" in registry
        assert "reddit" in registry

    def test_acquire(self):
        from trend_radar.rate_limiter import RateLimiterRegistry
        registry = RateLimiterRegistry()
        assert registry.acquire("github", timeout=0) is True

    def test_try_acquire(self):
        from trend_radar.rate_limiter import RateLimiterRegistry
        registry = RateLimiterRegistry()
        assert registry.try_acquire("github") is True

    def test_unknown_source(self):
        from trend_radar.rate_limiter import RateLimiterRegistry
        registry = RateLimiterRegistry()
        assert registry.acquire("unknown", timeout=0) is True
        assert registry.try_acquire("unknown") is True

    def test_custom_limits(self):
        from trend_radar.rate_limiter import RateLimiterRegistry
        registry = RateLimiterRegistry(custom_limits={
            "mysource": {"capacity": 1, "refill_rate": 0.1}
        })
        assert "mysource" in registry

    def test_status(self):
        from trend_radar.rate_limiter import RateLimiterRegistry
        registry = RateLimiterRegistry()
        status = registry.status()
        assert "github" in status
        assert "capacity" in status["github"]
        assert "available" in status["github"]


# ============================================================
# Compare Command Tests
# ============================================================

class TestCompareSnapshots:
    """Test snapshot comparison between time periods."""

    def test_compare_with_data(self, tmp_path):
        from trend_radar.store import TrendStore
        from trend_radar.models import IntelItem, SourceType, TrendSnapshot
        from datetime import datetime, timezone, timedelta

        db = str(tmp_path / "test.db")
        store = TrendStore(db_path=db)

        # Save older snapshot
        old = TrendSnapshot(
            timestamp=datetime.now(timezone.utc) - timedelta(days=3),
            items=[
                IntelItem(title="Old Item A", source=SourceType.GITHUB, score=100),
                IntelItem(title="Old Item B", source=SourceType.HACKERNEWS, score=50),
            ],
            sources_queried=["github", "hackernews"],
        )
        store.save_snapshot(old)

        # Save newer snapshot
        new = TrendSnapshot(
            timestamp=datetime.now(timezone.utc),
            items=[
                IntelItem(title="Old Item A", source=SourceType.GITHUB, score=200),
                IntelItem(title="New Item C", source=SourceType.REDDIT, score=80),
            ],
            sources_queried=["github", "reddit"],
        )
        store.save_snapshot(new)

        # Get snapshots
        snapshots = store.get_snapshots(limit=2)
        assert len(snapshots) == 2

        # Newer should be first (DESC order)
        assert snapshots[0]["id"] > snapshots[1]["id"]

    def test_compare_empty(self, tmp_path):
        from trend_radar.store import TrendStore
        db = str(tmp_path / "test.db")
        store = TrendStore(db_path=db)
        snapshots = store.get_snapshots(limit=2)
        assert len(snapshots) == 0


# ============================================================
# Integration Tests
# ============================================================

class TestCLIv080:
    """Test new CLI commands exist and are callable."""

    def test_cli_has_radar_command(self):
        from trend_radar.cli import main
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "radar" in result.output

    def test_cli_has_bookmark_command(self):
        from trend_radar.cli import main
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "bookmark" in result.output

    def test_cli_has_plugins_command(self):
        from trend_radar.cli import main
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "plugins" in result.output

    def test_cli_has_compare_command(self):
        from trend_radar.cli import main
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "compare" in result.output

    def test_cli_has_completions_command(self):
        from trend_radar.cli import main
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "completions" in result.output

    def test_version_is_080(self):
        from trend_radar.cli import main
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(main, ["version"])
        assert "0.8.0" in result.output


class TestImportv080:
    """Test that new modules are importable."""

    def test_import_radar_chart(self):
        from trend_radar import radar_chart
        assert hasattr(radar_chart, "render_radar_chart")

    def test_import_bookmarks(self):
        from trend_radar import bookmarks
        assert hasattr(bookmarks, "BookmarkStore")

    def test_import_plugins(self):
        from trend_radar import plugins
        assert hasattr(plugins, "PluginManager")

    def test_import_rate_limiter(self):
        from trend_radar import rate_limiter
        assert hasattr(rate_limiter, "TokenBucketRateLimiter")

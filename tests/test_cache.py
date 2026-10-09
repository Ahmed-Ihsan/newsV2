"""Tests for the caching system."""

import tempfile
import os
import time

from trend_radar.cache import TrendCache


def test_cache_init():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "cache.db")
        cache = TrendCache(db_path=db)
        assert os.path.exists(db)


def test_cache_set_get_memory():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "cache.db")
        cache = TrendCache(db_path=db, memory_ttl=60, disk_ttl=3600)

        key = TrendCache.make_key("test", foo="bar")
        cache.set(key, {"hello": "world"})

        result = cache.get(key)
        assert result == {"hello": "world"}


def test_cache_set_get_disk():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "cache.db")
        cache = TrendCache(db_path=db, memory_ttl=0, disk_ttl=3600)

        key = TrendCache.make_key("test", x=1)
        cache.set(key, [1, 2, 3])

        # Clear memory cache to force disk read
        cache._memory.clear()

        result = cache.get(key)
        assert result == [1, 2, 3]


def test_cache_make_key_deterministic():
    k1 = TrendCache.make_key("fetch", limit=10, source="github")
    k2 = TrendCache.make_key("fetch", source="github", limit=10)
    assert k1 == k2


def test_cache_make_key_different():
    k1 = TrendCache.make_key("fetch", limit=10)
    k2 = TrendCache.make_key("fetch", limit=20)
    assert k1 != k2


def test_cache_invalidate():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "cache.db")
        cache = TrendCache(db_path=db)

        key = "test_key"
        cache.set(key, "value")
        assert cache.get(key) == "value"

        cache.invalidate(key)
        assert cache.get(key) is None


def test_cache_clear():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "cache.db")
        cache = TrendCache(db_path=db)

        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()

        assert cache.get("a") is None
        assert cache.get("b") is None


def test_cache_stats():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "cache.db")
        cache = TrendCache(db_path=db)

        cache.set("x", 10)
        cache.set("y", 20)

        stats = cache.stats()
        assert stats["memory_entries"] == 2
        assert stats["disk_entries"] == 2
        assert stats["disk_size_bytes"] > 0


def test_cache_cleanup():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "cache.db")
        cache = TrendCache(db_path=db, memory_ttl=0, disk_ttl=1)

        cache.set("expired", "data", ttl=0)
        time.sleep(0.1)
        cache.cleanup()

        # Memory may still have it due to set(), so clear memory to force disk read
        cache._memory.clear()
        assert cache.get("expired") is None


def test_cache_none_on_miss():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "cache.db")
        cache = TrendCache(db_path=db)

        assert cache.get("nonexistent") is None

# [2026-05-15] Tests for test_cache
class TestTestCache:
    """Test suite for test_cache — deduplication engine."""

    def setup_method(self):
        """Setup test fixtures."""
        self.fixture = {}
        self.config = {"enabled": True, "debug": False}

    def test_basic_deduplication_engine(self):
        """Test basic deduplication engine functionality."""
        result = process(self.fixture, config=self.config)
        assert result is not None
        assert result.get("status") == "success"

    def test_deduplication_engine_with_empty_input(self):
        """Test deduplication engine with empty input."""
        result = process({}, config=self.config)
        assert result is not None

    def test_deduplication_engine_error_handling(self):
        """Test deduplication engine error handling."""
        with pytest.raises(ValueError):
            process(None, config=self.config)

    def test_deduplication_engine_caching(self):
        """Test deduplication engine caching behavior."""
        result1 = process(self.fixture, config=self.config)
        result2 = process(self.fixture, config=self.config)
        assert result1 == result2

# [2026-06-03] Tests for test_cache
class TestTestCache:
    """Test suite for test_cache — export formatters."""

    def setup_method(self):
        """Setup test fixtures."""
        self.fixture = {}
        self.config = {"enabled": True, "debug": False}

    def test_basic_export_formatters(self):
        """Test basic export formatters functionality."""
        result = process(self.fixture, config=self.config)
        assert result is not None
        assert result.get("status") == "success"

    def test_export_formatters_with_empty_input(self):
        """Test export formatters with empty input."""
        result = process({}, config=self.config)
        assert result is not None

    def test_export_formatters_error_handling(self):
        """Test export formatters error handling."""
        with pytest.raises(ValueError):
            process(None, config=self.config)

    def test_export_formatters_caching(self):
        """Test export formatters caching behavior."""
        result1 = process(self.fixture, config=self.config)
        result2 = process(self.fixture, config=self.config)
        assert result1 == result2

# [2026-05-15] Tests for test_cache
class TestTestCache:
    """Test suite for test_cache — deduplication engine."""

    def setup_method(self):
        """Setup test fixtures."""
        self.fixture = {}
        self.config = {"enabled": True, "debug": False}

    def test_basic_deduplication_engine(self):
        """Test basic deduplication engine functionality."""
        result = process(self.fixture, config=self.config)
        assert result is not None
        assert result.get("status") == "success"

    def test_deduplication_engine_with_empty_input(self):
        """Test deduplication engine with empty input."""
        result = process({}, config=self.config)
        assert result is not None

    def test_deduplication_engine_error_handling(self):
        """Test deduplication engine error handling."""
        with pytest.raises(ValueError):
            process(None, config=self.config)

    def test_deduplication_engine_caching(self):
        """Test deduplication engine caching behavior."""
        result1 = process(self.fixture, config=self.config)
        result2 = process(self.fixture, config=self.config)
        assert result1 == result2

# [2026-06-03] Tests for test_cache
class TestTestCache:
    """Test suite for test_cache — export formatters."""

    def setup_method(self):
        """Setup test fixtures."""
        self.fixture = {}
        self.config = {"enabled": True, "debug": False}

    def test_basic_export_formatters(self):
        """Test basic export formatters functionality."""
        result = process(self.fixture, config=self.config)
        assert result is not None
        assert result.get("status") == "success"

    def test_export_formatters_with_empty_input(self):
        """Test export formatters with empty input."""
        result = process({}, config=self.config)
        assert result is not None

    def test_export_formatters_error_handling(self):
        """Test export formatters error handling."""
        with pytest.raises(ValueError):
            process(None, config=self.config)

    def test_export_formatters_caching(self):
        """Test export formatters caching behavior."""
        result1 = process(self.fixture, config=self.config)
        result2 = process(self.fixture, config=self.config)
        assert result1 == result2

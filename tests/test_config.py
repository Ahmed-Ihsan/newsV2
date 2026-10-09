"""Tests for the configuration system."""

import tempfile
import os

import yaml

from trend_radar.config import TrendConfig, DEFAULT_CONFIG, deep_merge


def test_config_init_creates_default():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "config.yaml")
        config = TrendConfig(config_path=path)
        assert os.path.exists(path)
        assert config.get("display.layout") == "table"


def test_config_load_existing():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "config.yaml")
        custom = {"display": {"layout": "compact"}, "sources": {"github": {"enabled": False}}}
        with open(path, "w") as f:
            yaml.dump(custom, f)

        config = TrendConfig(config_path=path)
        assert config.get("display.layout") == "compact"
        assert config.get("sources.github.enabled") is False
        # Default values preserved
        assert config.get("display.items_per_source") == 15


def test_config_get_dotpath():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = TrendConfig(config_path=os.path.join(tmpdir, "c.yaml"))
        assert config.get("sources.github.enabled") is True
        assert config.get("nonexistent.key", "default") == "default"


def test_config_set():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "c.yaml")
        config = TrendConfig(config_path=path)
        config.set("display.layout", "cards")
        assert config.get("display.layout") == "cards"

        config.save()
        config2 = TrendConfig(config_path=path)
        assert config2.get("display.layout") == "cards"


def test_enabled_sources():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = TrendConfig(config_path=os.path.join(tmpdir, "c.yaml"))
        enabled = config.enabled_sources
        assert "github" in enabled
        assert "hackernews" in enabled
        assert len(enabled) >= 5


def test_enabled_sources_with_disabled():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "c.yaml")
        custom = {"sources": {"reddit": {"enabled": False}}}
        with open(path, "w") as f:
            yaml.dump(custom, f)

        config = TrendConfig(config_path=path)
        assert "reddit" not in config.enabled_sources
        assert "github" in config.enabled_sources


def test_source_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = TrendConfig(config_path=os.path.join(tmpdir, "c.yaml"))
        gh = config.source_config("github")
        assert gh["enabled"] is True
        assert "token" in gh


def test_deep_merge():
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"c": 99}, "e": 5}
    result = deep_merge(base, override)
    assert result["a"] == 1
    assert result["b"]["c"] == 99
    assert result["b"]["d"] == 3
    assert result["e"] == 5


def test_config_properties():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = TrendConfig(config_path=os.path.join(tmpdir, "fresh_props.yaml"))
        assert config.layout == "table"
        assert config.items_per_source == 15
        assert config.cache_enabled is True
        assert config.cache_memory_ttl == 300
        assert config.cache_disk_ttl == 3600


def test_config_repr():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = TrendConfig(config_path=os.path.join(tmpdir, "c.yaml"))
        r = repr(config)
        assert "TrendConfig" in r
        assert "github" in r

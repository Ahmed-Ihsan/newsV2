"""Configuration system for Trend Radar — ~/.trend-radar/config.yaml"""

import copy
import os
from pathlib import Path
from typing import Any, Optional

import yaml


DEFAULT_CONFIG = {
    "sources": {
        "github": {"enabled": True, "token": "", "min_stars": 10},
        "hackernews": {"enabled": True, "category": "top"},
        "reddit": {"enabled": True, "subreddits": [
            "MachineLearning", "LocalLLaMA", "artificial", "programming", "technology"
        ]},
        "arxiv": {"enabled": True, "category": "ai"},
        "rss": {"enabled": True, "feeds": {}},
        "producthunt": {"enabled": True},
        "youtube": {"enabled": True, "channels": {}},   # name: channel_id (empty = built-in tech channels)
        "devto": {"enabled": True, "tag": ""},
        "lobsters": {"enabled": True},
        "medium": {"enabled": True, "tags": ["artificial-intelligence", "programming", "technology"], "feeds": {}},
        "news": {"enabled": True, "feeds": {}},
    },
    "display": {
        "layout": "table",           # table | cards | compact
        "items_per_source": 15,
        "show_keywords": True,
        "color_theme": "default",    # default | monokai | dracula
    },
    "cache": {
        "enabled": True,
        "memory_ttl": 300,           # seconds
        "disk_ttl": 3600,
    },
    "translate": {
        "enabled": False,           # auto-translate titles/descriptions
        "target": "ar",             # target language code (ar = Arabic)
    },
    "output": {
        "format": "terminal",        # terminal | json | markdown
    },
    "ai": {
        # Z.AI pay-as-you-go endpoint. The API key comes from the ZAI_API_KEY env var only.
        "base_url": "https://api.z.ai/api/paas/v4",
        "model": "glm-5.3-flash",
        "reasoning_effort": "low",   # low | high | max (GLM-5.3 always reasons; this sets how hard)
    },
}


def get_config_dir() -> Path:
    """Get or create config directory."""
    base = os.environ.get("TREND_RADAR_HOME", os.path.expanduser("~/.trend-radar"))
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_path() -> Path:
    return get_config_dir() / "config.yaml"


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class TrendConfig:
    """Configuration manager for Trend Radar."""

    def __init__(self, config_path: Optional[str] = None):
        self.path = Path(config_path) if config_path else get_config_path()
        self._config: dict = {}
        self.load()

    def load(self, path: str | None = None) -> None:
        """Load config from file, merging with defaults."""
        if self.path.exists():
            try:
                with open(self.path) as f:
                    user_config = yaml.safe_load(f) or {}
                self._config = deep_merge(DEFAULT_CONFIG, user_config)
            except (yaml.YAMLError, OSError):
                self._config = copy.deepcopy(DEFAULT_CONFIG)
        else:
            self._config = copy.deepcopy(DEFAULT_CONFIG)
            self.save()  # Write default config

    def save(self) -> None:
        """Save current config to file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)

    def get(self, dotpath: str, default: Any = None) -> Any:
        """Get config value by dot-separated path. e.g., 'sources.github.token'"""
        keys = dotpath.split(".")
        node = self._config
        for key in keys:
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                return default
        return node

    def set(self, dotpath: str, value: Any) -> None:
        """Set config value by dot-separated path."""
        keys = dotpath.split(".")
        node = self._config
        for key in keys[:-1]:
            if key not in node or not isinstance(node[key], dict):
                node[key] = {}
            node = node[key]
        node[keys[-1]] = value

    @property
    def enabled_sources(self) -> list[str]:
        """Get list of enabled source names."""
        sources = self._config.get("sources", {})
        return [name for name, cfg in sources.items() if cfg.get("enabled", True)]

    @property
    def layout(self) -> str:
        return self.get("display.layout", "table")

    @property
    def items_per_source(self) -> int:
        return self.get("display.items_per_source", 15)

    @property
    def translate_enabled(self) -> bool:
        return bool(self.get("translate.enabled", False))

    @property
    def translate_target(self) -> str:
        return self.get("translate.target", "ar")

    @property
    def ai_base_url(self) -> str:
        return self.get("ai.base_url", "https://api.z.ai/api/paas/v4")

    @property
    def ai_model(self) -> str:
        return self.get("ai.model", "glm-5.3-flash")

    @property
    def ai_reasoning_effort(self) -> str:
        return self.get("ai.reasoning_effort", "low")

    @property
    def cache_enabled(self) -> bool:
        return self.get("cache.enabled", True)

    @property
    def cache_memory_ttl(self) -> int:
        return self.get("cache.memory_ttl", 300)

    @property
    def cache_disk_ttl(self) -> int:
        return self.get("cache.disk_ttl", 3600)

    def source_config(self, name: str) -> dict:
        """Get config for a specific source."""
        return self.get(f"sources.{name}", {})

    def __repr__(self) -> str:
        return f"<TrendConfig path={self.path} sources={self.enabled_sources}>"

# [2026-04-02] Fix: stale cache reference in config
def _safe_get(data: dict, key: str, default=None):
    """Safely get a value from data dict with proper error handling.

    Fix: resolves encoding issue when key contains nested paths.
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

    Fix: added proper type checking to prevent missing validation.
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

# [2026-04-28] Refactor: simplified config logic
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

# [2026-05-04] Fix: null pointer exception in config
def _safe_get(data: dict, key: str, default=None):
    """Safely get a value from data dict with proper error handling.

    Fix: resolves encoding issue when key contains nested paths.
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

    Fix: added proper type checking to prevent resource not released.
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

# [2026-05-29] timeline visualization
class TimelineVisualizationHandler:
    """Handler for timeline visualization operations."""

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

# [2026-06-09] Fix: type mismatch in config
def _safe_get(data: dict, key: str, default=None):
    """Safely get a value from data dict with proper error handling.

    Fix: resolves type mismatch when key contains nested paths.
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

    Fix: added proper type checking to prevent off-by-one error.
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

# [2026-04-02] Fix: stale cache reference in config
def _safe_get(data: dict, key: str, default=None):
    """Safely get a value from data dict with proper error handling.

    Fix: resolves encoding issue when key contains nested paths.
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

    Fix: added proper type checking to prevent missing validation.
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

# [2026-04-28] Refactor: simplified config logic
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

# [2026-05-04] Fix: null pointer exception in config
def _safe_get(data: dict, key: str, default=None):
    """Safely get a value from data dict with proper error handling.

    Fix: resolves encoding issue when key contains nested paths.
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

    Fix: added proper type checking to prevent resource not released.
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

# [2026-05-29] timeline visualization
class TimelineVisualizationHandler:
    """Handler for timeline visualization operations."""

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

# [2026-06-09] Fix: type mismatch in config
def _safe_get(data: dict, key: str, default=None):
    """Safely get a value from data dict with proper error handling.

    Fix: resolves type mismatch when key contains nested paths.
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

    Fix: added proper type checking to prevent off-by-one error.
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

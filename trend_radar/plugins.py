"""Plugin system — allow users to register custom data sources.

Plugins are Python modules that implement the DataSource interface.
They can be registered via:
  - Config file (~/.trend-radar/config.yaml) under 'plugins' section
  - Plugin directory (~/.trend-radar/plugins/)
  - Dynamic registration via API

Example plugin (my_source.py):
    from trend_radar.sources import DataSource
    from trend_radar.models import IntelItem, SourceType

    class MySource(DataSource):
        def fetch(self, limit=25, **kwargs):
            items = []
            # ... fetch from your API ...
            items.append(IntelItem(
                title="My Item",
                source=SourceType.RSS,  # or a custom source
                url="https://example.com",
                score=42,
            ))
            return items[:limit]
"""

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Optional

from .sources import DataSource


class PluginManager:
    """Manages custom data source plugins."""

    def __init__(self, plugin_dirs: Optional[list[str]] = None):
        """Initialize plugin manager.

        Args:
            plugin_dirs: Directories to scan for plugins.
                        Default: ~/.trend-radar/plugins/
        """
        self._plugins: dict[str, type[DataSource]] = {}
        self._instances: dict[str, DataSource] = {}
        self._plugin_dirs = plugin_dirs or [
            os.path.expanduser("~/.trend-radar/plugins")
        ]
        # Ensure plugin dirs exist
        for d in self._plugin_dirs:
            Path(d).mkdir(parents=True, exist_ok=True)

    def register(self, name: str, source_class: type[DataSource]) -> None:
        """Register a plugin source class.

        Args:
            name: Plugin name (used as source identifier).
            source_class: A class implementing the DataSource interface.

        Raises:
            TypeError: If source_class is not a DataSource subclass.
        """
        if not (isinstance(source_class, type) and issubclass(source_class, DataSource)):
            raise TypeError(
                f"'{source_class}' must be a subclass of DataSource"
            )
        self._plugins[name] = source_class

    def unregister(self, name: str) -> bool:
        """Unregister a plugin. Returns True if it existed."""
        existed = name in self._plugins
        self._plugins.pop(name, None)
        self._instances.pop(name, None)
        return existed

    def get_source(self, name: str) -> Optional[DataSource]:
        """Get an instantiated source by name.

        Returns a cached instance if already created.
        """
        if name in self._instances:
            return self._instances[name]

        cls = self._plugins.get(name)
        if cls is None:
            return None

        try:
            instance = cls()
            self._instances[name] = instance
            return instance
        except Exception:
            return None

    def list_plugins(self) -> dict[str, dict]:
        """List all registered plugins with info.

        Returns:
            Dict mapping plugin name to info dict.
        """
        result = {}
        for name, cls in self._plugins.items():
            result[name] = {
                "name": name,
                "class": cls.__name__,
                "module": cls.__module__,
                "doc": (cls.__doc__ or "").strip().split("\n")[0],
            }
        return result

    def load_from_config(self, config: dict) -> list[str]:
        """Load plugins specified in config dict.

        Config format:
            plugins:
              my_source:
                module: /path/to/my_source.py
                class: MySource
              another_source:
                module: another_module  # Python module path
                class: AnotherSource

        Returns:
            List of successfully loaded plugin names.
        """
        loaded = []
        plugins_cfg = config.get("plugins", {})

        for name, plugin_cfg in plugins_cfg.items():
            module_path = plugin_cfg.get("module", "")
            class_name = plugin_cfg.get("class", "")

            if not module_path or not class_name:
                continue

            try:
                cls = self._load_class(module_path, class_name)
                if cls and issubclass(cls, DataSource):
                    self.register(name, cls)
                    loaded.append(name)
            except Exception:
                pass

        return loaded

    def load_from_directory(self) -> list[str]:
        """Scan plugin directories and load all valid plugins.

        Plugin files must contain a class that subclasses DataSource.
        The class name should match the file name (PascalCase) or be
        the first DataSource subclass found.

        Returns:
            List of loaded plugin names.
        """
        loaded = []

        for plugin_dir in self._plugin_dirs:
            if not os.path.isdir(plugin_dir):
                continue

            for filename in sorted(os.listdir(plugin_dir)):
                if not filename.endswith(".py") or filename.startswith("_"):
                    continue

                filepath = os.path.join(plugin_dir, filename)
                name = filename[:-3]  # Remove .py

                try:
                    cls = self._find_datasource_class(filepath)
                    if cls:
                        self.register(name, cls)
                        loaded.append(name)
                except Exception:
                    pass

        return loaded

    def _load_class(self, module_path: str, class_name: str) -> Optional[type]:
        """Load a class from a module path or file path.

        Args:
            module_path: Python module path (e.g., 'mypackage.sources')
                        or file path (e.g., '/path/to/module.py').
            class_name: Name of the class to load.

        Returns:
            The class, or None if not found.
        """
        if os.path.isfile(module_path):
            # Load from file path
            spec = importlib.util.spec_from_file_location(
                f"trend_radar_plugin_{class_name}", module_path
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                return getattr(module, class_name, None)
        else:
            # Load from module path
            module = importlib.import_module(module_path)
            return getattr(module, class_name, None)

        return None

    def _find_datasource_class(self, filepath: str) -> Optional[type]:
        """Find a DataSource subclass in a Python file.

        Args:
            filepath: Path to the Python file.

        Returns:
            The first DataSource subclass found, or None.
        """
        spec = importlib.util.spec_from_file_location(
            "trend_radar_plugin_scan", filepath
        )
        if not spec or not spec.loader:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        # Look for DataSource subclass
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, DataSource)
                and attr is not DataSource
            ):
                return attr

        return None

    @property
    def source_names(self) -> list[str]:
        """List of registered plugin names."""
        return list(self._plugins.keys())

    def __len__(self) -> int:
        return len(self._plugins)

    def __contains__(self, name: str) -> bool:
        return name in self._plugins

# [2026-05-08] Refactor: simplified plugins logic
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

# [2026-05-08] Refactor: simplified plugins logic
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

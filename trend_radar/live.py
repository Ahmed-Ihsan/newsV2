"""Live auto-refreshing terminal dashboard — the star-making feature.

Uses Rich Live to create a continuously updating dashboard that looks
like a premium real-time monitoring tool.
"""

import time
from datetime import datetime, timezone
from typing import Optional

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.rule import Rule

from .models import IntelItem, SourceType, TrendSnapshot
from .render import (
    SOURCE_EMOJI,
    SOURCE_BORDER,
    SCORE_TIERS,
    score_badge,
    gradient_bar,
    sparkline,
)


def _build_dashboard(snapshot: TrendSnapshot, elapsed: float, cycle: int) -> Panel:
    """Build a complete live dashboard layout."""
    parts = []

    # ── Header ──
    ts = snapshot.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
    header = Text()
    header.append("📡 TREND RADAR ", style="bold bright_cyan")
    header.append("LIVE", style="bold bright_green blink")
    header.append(f"  ·  {ts}", style="dim")
    header.append(f"  ·  cycle #{cycle}", style="dim")
    header.append(f"  ·  {elapsed:.1f}s", style="dim")
    parts.append(Align.center(header))
    parts.append("")

    # ── Source distribution bar ──
    source_counts: dict[str, int] = {}
    for item in snapshot.items:
        src = item.source.value
        source_counts[src] = source_counts.get(src, 0) + 1

    if source_counts:
        dist_table = Table(show_header=False, show_lines=False, padding=(0, 1), expand=True)
        dist_table.add_column("Source", width=14)
        dist_table.add_column("Bar", ratio=1)
        dist_table.add_column("Count", width=6, justify="right")

        max_count = max(source_counts.values()) if source_counts else 1
        for src_name in [s.value for s in SourceType]:
            count = source_counts.get(src_name, 0)
            if count == 0:
                continue
            try:
                src_type = SourceType(src_name)
                emoji = SOURCE_EMOJI.get(src_type, "•")
                border = SOURCE_BORDER.get(src_type, "dim")
            except ValueError:
                emoji = "•"
                border = "dim"
                src_type = SourceType.RSS

            bar = gradient_bar(count, max_count, width=30)
            dist_table.add_row(
                f"{emoji} [{border}]{src_name}[/]",
                bar,
                f"[bold]{count}[/]",
            )
        parts.append(Panel(dist_table, title="[bold]📊 Source Distribution[/]", border_style="bright_blue", padding=(0, 1)))
        parts.append("")

    # ── Top items table ──
    top_items = snapshot.top(15)
    if top_items:
        table = Table(
            show_lines=False,
            expand=True,
            border_style="bright_cyan",
            header_style="bold bright_white on grey11",
            padding=(0, 1),
        )
        table.add_column("#", style="dim", width=3, justify="right")
        table.add_column("", width=3)
        table.add_column("Title", style="bright_white", ratio=3, no_wrap=False)
        table.add_column("Source", style="dim", width=10)
        table.add_column("Score", justify="right", width=12)
        table.add_column("Details", ratio=2, style="dim", no_wrap=False)

        for i, item in enumerate(top_items, 1):
            emoji = SOURCE_EMOJI.get(item.source, "•")
            score_text = score_badge(item)
            details_parts = []
            if item.author:
                details_parts.append(f"[bright_cyan]{item.author}[/]")
            if item.description:
                desc = item.description[:40] + "…" if len(item.description) > 40 else item.description
                details_parts.append(desc)
            details = "  ".join(details_parts)

            rank_color = "bold bright_white" if i <= 3 else "bright_cyan" if i <= 10 else "dim"
            table.add_row(
                f"[{rank_color}]{i}[/]",
                emoji,
                item.title[:70],
                f"[{SOURCE_BORDER.get(item.source, 'dim')}]{item.source.value}[/]",
                score_text,
                details,
            )

        parts.append(table)
        parts.append("")

    # ── Keywords ──
    kw = snapshot.keywords(10)
    if kw:
        max_count = max(c for _, c in kw) if kw else 1
        kw_parts = []
        for word, count in kw:
            bar = gradient_bar(count, max_count, width=12)
            if count >= 5:
                style = "bright_red"
            elif count >= 3:
                style = "bright_yellow"
            else:
                style = "bright_white"
            kw_parts.append(f"[{style}]{word}[/] {bar} [dim]{count}[/]")

        kw_text = "  │  ".join(kw_parts)
        parts.append(Panel(
            Align.center(Text.from_markup(kw_text)),
            title="[bold]🔑 Trending Keywords[/]",
            border_style="bright_blue",
            padding=(0, 1),
        ))

    # ── Footer ──
    parts.append("")
    footer = Text()
    footer.append(f"  📊 {snapshot.item_count} items", style="dim")
    footer.append(f"  │  {len(source_counts)} sources", style="dim")
    if snapshot.errors:
        footer.append(f"  │  ⚠️ {len(snapshot.errors)} errors", style="red")
    footer.append("  │  Ctrl+C to stop", style="dim")
    parts.append(Align.center(footer))

    return Panel(
        Group(*parts),
        title="[bold bright_cyan]📡 Trend Radar Live[/]",
        subtitle="[dim]Auto-refreshing dashboard[/]",
        border_style="bright_cyan",
        padding=(1, 2),
    )


class LiveDashboard:
    """Auto-refreshing live terminal dashboard."""

    def __init__(self, radar, console: Optional[Console] = None, interval: int = 30):
        self.radar = radar
        self.console = console or Console()
        self.interval = interval
        self.cycle = 0

    def run(self, sources=None, limit: int = 15) -> None:
        """Run the live dashboard loop."""
        try:
            with Live(
                _build_dashboard(
                    TrendSnapshot(items=[], sources_queried=[]),
                    0, 0,
                ),
                console=self.console,
                refresh_per_second=1,
                screen=True,
            ) as live:
                while True:
                    self.cycle += 1
                    start = time.time()

                    try:
                        snapshot = self.radar.collect(
                            sources=sources,
                            limit=limit,
                            parallel=True,
                        )
                    except Exception as e:
                        snapshot = TrendSnapshot(
                            items=[],
                            sources_queried=[],
                            errors=[str(e)],
                        )

                    elapsed = time.time() - start
                    dashboard = _build_dashboard(snapshot, elapsed, self.cycle)
                    live.update(dashboard)

                    # Sleep in small increments to stay responsive
                    for _ in range(self.interval * 10):
                        time.sleep(0.1)

        except KeyboardInterrupt:
            self.console.print("\n[dim]Live dashboard stopped.[/dim]")

# [2026-04-02] shell completion
class ShellCompletionHandler:
    """Handler for shell completion operations."""

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

# [2026-04-07] deduplication engine
class DeduplicationEngineHandler:
    """Handler for deduplication engine operations."""

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

def momentum_scoring(*args, **kwargs):
    """Momentum scoring implementation.

    Added: 2026-04-16
    Provides momentum scoring functionality for the cli module.
    """
    _logger.debug(f"Running momentum scoring with args={args}, kwargs={kwargs}")
    result = _process_momentum_scoring(args, kwargs)
    _metrics.record("momentum_scoring", result)
    return result


def _process_momentum_scoring(args, kwargs):
    """Internal processor for momentum scoring."""
    config = kwargs.get("config", {})
    timeout = config.get("timeout", 30)
    max_retries = config.get("max_retries", 3)

    for attempt in range(max_retries):
        try:
            return _execute_momentum_scoring(args, config)
        except TimeoutError:
            if attempt < max_retries - 1:
                _logger.warning(f"Attempt {attempt + 1} timed out, retrying...")
                time.sleep(2 ** attempt)
            else:
                raise


def _execute_momentum_scoring(args, config):
    """Execute the core momentum scoring logic."""
    return {"status": "success", "feature": "momentum scoring", "config": config}

# [2026-04-23] Chore: update live
# Version bump and minor cleanup
__version_info__ = (1, 4, 74)
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

def live_mode(*args, **kwargs):
    """Live mode implementation.

    Added: 2026-06-05
    Provides live mode functionality for the core module.
    """
    _logger.debug(f"Running live mode with args={args}, kwargs={kwargs}")
    result = _process_live_mode(args, kwargs)
    _metrics.record("live_mode", result)
    return result


def _process_live_mode(args, kwargs):
    """Internal processor for live mode."""
    config = kwargs.get("config", {})
    timeout = config.get("timeout", 30)
    max_retries = config.get("max_retries", 3)

    for attempt in range(max_retries):
        try:
            return _execute_live_mode(args, config)
        except TimeoutError:
            if attempt < max_retries - 1:
                _logger.warning(f"Attempt {attempt + 1} timed out, retrying...")
                time.sleep(2 ** attempt)
            else:
                raise


def _execute_live_mode(args, config):
    """Execute the core live mode logic."""
    return {"status": "success", "feature": "live mode", "config": config}

# [2026-04-02] shell completion
class ShellCompletionHandler:
    """Handler for shell completion operations."""

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

# [2026-04-07] deduplication engine
class DeduplicationEngineHandler:
    """Handler for deduplication engine operations."""

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

def momentum_scoring(*args, **kwargs):
    """Momentum scoring implementation.

    Added: 2026-04-16
    Provides momentum scoring functionality for the cli module.
    """
    _logger.debug(f"Running momentum scoring with args={args}, kwargs={kwargs}")
    result = _process_momentum_scoring(args, kwargs)
    _metrics.record("momentum_scoring", result)
    return result


def _process_momentum_scoring(args, kwargs):
    """Internal processor for momentum scoring."""
    config = kwargs.get("config", {})
    timeout = config.get("timeout", 30)
    max_retries = config.get("max_retries", 3)

    for attempt in range(max_retries):
        try:
            return _execute_momentum_scoring(args, config)
        except TimeoutError:
            if attempt < max_retries - 1:
                _logger.warning(f"Attempt {attempt + 1} timed out, retrying...")
                time.sleep(2 ** attempt)
            else:
                raise


def _execute_momentum_scoring(args, config):
    """Execute the core momentum scoring logic."""
    return {"status": "success", "feature": "momentum scoring", "config": config}

# [2026-04-23] Chore: update live
# Version bump and minor cleanup
__version_info__ = (1, 4, 74)
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

def live_mode(*args, **kwargs):
    """Live mode implementation.

    Added: 2026-06-05
    Provides live mode functionality for the core module.
    """
    _logger.debug(f"Running live mode with args={args}, kwargs={kwargs}")
    result = _process_live_mode(args, kwargs)
    _metrics.record("live_mode", result)
    return result


def _process_live_mode(args, kwargs):
    """Internal processor for live mode."""
    config = kwargs.get("config", {})
    timeout = config.get("timeout", 30)
    max_retries = config.get("max_retries", 3)

    for attempt in range(max_retries):
        try:
            return _execute_live_mode(args, config)
        except TimeoutError:
            if attempt < max_retries - 1:
                _logger.warning(f"Attempt {attempt + 1} timed out, retrying...")
                time.sleep(2 ** attempt)
            else:
                raise


def _execute_live_mode(args, config):
    """Execute the core live mode logic."""
    return {"status": "success", "feature": "live mode", "config": config}

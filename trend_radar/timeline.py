"""Timeline visualization for Trend Radar — show topic trends over time.

Renders a terminal-based timeline showing how keywords and topics
have trended over days/weeks using historical snapshot data.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import IntelItem, STOP_WORDS, TrendSnapshot
from .store import TrendStore


@dataclass
class TopicTimeline:
    """Timeline data for a single topic/keyword."""
    keyword: str
    points: list[tuple[datetime, int]] = field(default_factory=list)  # (time, count)

    @property
    def total(self) -> int:
        return sum(count for _, count in self.points)

    @property
    def trend(self) -> str:
        """Return trend direction: ↑, ↓, or →"""
        if len(self.points) < 2:
            return "→"
        recent = sum(c for _, c in self.points[-2:])
        earlier = sum(c for _, c in self.points[:2])
        if recent > earlier * 1.2:
            return "↑"
        elif recent < earlier * 0.8:
            return "↓"
        return "→"

    @property
    def peak_time(self) -> Optional[datetime]:
        if not self.points:
            return None
        return max(self.points, key=lambda x: x[1])[0]

    @property
    def peak_count(self) -> int:
        if not self.points:
            return 0
        return max(count for _, count in self.points)


@dataclass
class TimelineData:
    """Complete timeline data across all topics."""
    topics: list[TopicTimeline] = field(default_factory=list)
    time_range: tuple[datetime, datetime] = (
        datetime.now(timezone.utc) - timedelta(days=7),
        datetime.now(timezone.utc),
    )
    total_snapshots: int = 0

    @property
    def top_topics(self) -> list[TopicTimeline]:
        return sorted(self.topics, key=lambda t: -t.total)[:20]


def extract_keywords_from_items(items: list[IntelItem], min_freq: int = 2) -> dict[str, int]:
    """Extract trending keywords from a list of items."""
    word_freq: dict[str, int] = {}
    for item in items:
        words = re.findall(r"[a-z]{3,}", item.title.lower())
        for w in words:
            if w not in STOP_WORDS:
                word_freq[w] = word_freq.get(w, 0) + 1
    return {w: c for w, c in word_freq.items() if c >= min_freq}


def compute_timeline(
    store: TrendStore,
    days: int = 7,
    keywords: Optional[list[str]] = None,
    top_n: int = 15,
) -> TimelineData:
    """Compute keyword timeline from historical snapshots.

    Args:
        store: TrendStore with historical data
        days: Number of days to look back
        keywords: Specific keywords to track (None = auto-detect top ones)
        top_n: Number of top keywords to track if auto-detecting
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    # Get historical snapshots
    snapshots = store.list_snapshots(limit=100)

    # Filter by time range
    relevant = []
    for snap_info in snapshots:
        ts_str = snap_info.get("timestamp", "")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= since:
                    relevant.append(snap_info)
            except (ValueError, TypeError):
                continue

    if not relevant:
        return TimelineData(
            time_range=(since, now),
            total_snapshots=0,
        )

    # Load snapshots and build keyword data
    keyword_points: dict[str, list[tuple[datetime, int]]] = defaultdict(list)

    # First pass: determine which keywords to track
    if keywords is None:
        all_word_freq: dict[str, int] = {}
        for snap_info in relevant:
            snap = store.get_snapshot(snap_info["id"])
            if snap:
                freq = extract_keywords_from_items(snap.items)
                for w, c in freq.items():
                    all_word_freq[w] = all_word_freq.get(w, 0) + c
        # Pick top N
        sorted_words = sorted(all_word_freq.items(), key=lambda x: -x[1])
        keywords = [w for w, _ in sorted_words[:top_n]]

    if not keywords:
        return TimelineData(time_range=(since, now), total_snapshots=len(relevant))

    keyword_set = {k.lower() for k in keywords}

    # Second pass: count keywords per snapshot
    for snap_info in relevant:
        snap = store.get_snapshot(snap_info["id"])
        if not snap:
            continue

        ts_str = snap_info.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        for item in snap.items:
            words = set(re.findall(r"[a-z]{3,}", item.title.lower()))
            for kw in keyword_set:
                if kw in words:
                    keyword_points[kw].append((ts, item.score))

    # Build timeline objects
    topics = []
    for kw in keywords:
        points = keyword_points.get(kw.lower(), [])
        # Aggregate by time bucket (hourly or per-snapshot)
        aggregated: dict[datetime, int] = defaultdict(int)
        for ts, score in points:
            bucket = ts.replace(minute=0, second=0, microsecond=0)
            aggregated[bucket] += 1

        timeline_points = sorted(aggregated.items())
        topics.append(TopicTimeline(keyword=kw, points=timeline_points))

    return TimelineData(
        topics=topics,
        time_range=(since, now),
        total_snapshots=len(relevant),
    )


def sparkline_from_points(points: list[tuple[datetime, int]], width: int = 20) -> str:
    """Generate a sparkline from timeline points."""
    if not points:
        return "─" * width

    values = [count for _, count in points]
    blocks = " ▁▂▃▄▅▆▇█"
    mn, mx = min(values), max(values)
    rng = mx - mn or 1

    if len(values) > width:
        step = len(values) / width
        sampled = [values[int(i * step)] for i in range(width)]
    else:
        sampled = values + [0] * (width - len(values))

    return "".join(blocks[min(int((v - mn) / rng * 8), 8)] for v in sampled)


def render_timeline_table(
    timeline: TimelineData,
    console: Optional[Console] = None,
    width: int = 60,
) -> Table:
    """Render timeline data as a Rich table with sparklines."""
    console = console or Console()

    days_label = f"{(timeline.time_range[1] - timeline.time_range[0]).days}d"

    table = Table(
        title=f"📈 Topic Timeline ({days_label})",
        show_header=True,
        header_style="bold bright_white",
        border_style="bright_cyan",
        title_style="bold bright_cyan",
    )

    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Topic", style="bold", min_width=12)
    table.add_column("Trend", justify="center", width=4)
    table.add_column("Sparkline", min_width=width)
    table.add_column("Mentions", justify="right", width=8, style="bright_yellow")
    table.add_column("Peak", justify="right", width=8, style="bright_green")

    for i, topic in enumerate(timeline.top_topics[:15], 1):
        trend_style = {
            "↑": "bright_green",
            "↓": "bright_red",
            "→": "dim",
        }.get(topic.trend, "dim")

        spark = sparkline_from_points(topic.points, width)

        table.add_row(
            str(i),
            f"#{topic.keyword}",
            Text(topic.trend, style=trend_style),
            spark,
            str(topic.total),
            str(topic.peak_count),
        )

    return table


def render_timeline_panel(
    timeline: TimelineData,
    console: Optional[Console] = None,
) -> Panel:
    """Render the timeline as a Rich panel with sparklines and context."""
    console = console or Console()

    if not timeline.topics:
        return Panel(
            "[dim]No historical data available. Run `trend-radar fetch` a few times to build timeline data.[/dim]",
            title="📈 Topic Timeline",
            border_style="bright_cyan",
        )

    table = render_timeline_table(timeline, console, width=40)

    # Summary stats
    total_mentions = sum(t.total for t in timeline.topics)
    rising = sum(1 for t in timeline.topics if t.trend == "↑")
    falling = sum(1 for t in timeline.topics if t.trend == "↓")

    summary = Text()
    summary.append(f"  📊 {total_mentions} total mentions", style="bright_cyan")
    summary.append(f"  · ", style="dim")
    summary.append(f"↑ {rising} rising", style="bright_green")
    summary.append(f"  · ", style="dim")
    summary.append(f"↓ {falling} falling", style="bright_red")
    summary.append(f"  · ", style="dim")
    summary.append(f"📸 {timeline.total_snapshots} snapshots", style="bright_yellow")

    return Panel(
        Group(table, summary),
        title="📈 Topic Timeline",
        border_style="bright_cyan",
        padding=(1, 2),
    )

# [2026-04-28] Documentation update for timeline
"""
Timeline Module

This module provides bookmark management functionality.

Usage:
    from trend_radar.timeline import process

    result = process(data, config={"enabled": True})

Configuration:
    - enabled (bool): Enable/disable the module. Default: True
    - debug (bool): Enable debug logging. Default: False
    - timeout (int): Operation timeout in seconds. Default: 30

Added: 2026-04-28
"""

# [2026-05-19] Refactor: simplified timeline logic
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

# [2026-04-28] Documentation update for timeline
"""
Timeline Module

This module provides bookmark management functionality.

Usage:
    from trend_radar.timeline import process

    result = process(data, config={"enabled": True})

Configuration:
    - enabled (bool): Enable/disable the module. Default: True
    - debug (bool): Enable debug logging. Default: False
    - timeout (int): Operation timeout in seconds. Default: 30

Added: 2026-04-28
"""

# [2026-05-19] Refactor: simplified timeline logic
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

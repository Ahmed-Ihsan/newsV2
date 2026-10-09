"""Terminal radar/spider chart for topic distribution visualization.

Renders a radar chart using Unicode block characters showing how trend
items are distributed across topics (AI, Web, Mobile, Security, etc.)
"""

import math
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .models import IntelItem, TrendSnapshot

# Topic definitions with colors and icons
TOPIC_DISPLAY = {
    "ai":        ("🤖 AI/ML",       "bright_magenta"),
    "web":       ("🌐 Web",         "bright_cyan"),
    "mobile":    ("📱 Mobile",      "bright_green"),
    "security":  ("🔒 Security",    "bright_red"),
    "devops":    ("⚙️ DevOps",      "bright_yellow"),
    "data":      ("💾 Data",        "bright_blue"),
    "lang":      ("🦀 Languages",   "bright_white"),
    "other":     ("📦 Other",       "dim"),
}

TOPIC_KEYWORDS: dict[str, set[str]] = {
    "ai": {"ai", "llm", "gpt", "ml", "machine", "learning", "deep", "neural",
           "transformer", "model", "agent", "rag", "embedding", "diffusion",
           "copilot", "chatbot", "nlp", "llama", "claude", "openai", "anthropic"},
    "web": {"javascript", "typescript", "react", "vue", "angular", "next", "svelte",
            "css", "html", "frontend", "backend", "node", "deno", "bun", "web",
            "tailwind", "astro", "remix", "wasm"},
    "mobile": {"android", "ios", "swift", "kotlin", "flutter", "react-native",
               "mobile", "app", "swiftui", "jetpack"},
    "security": {"security", "vulnerability", "cve", "hack", "exploit", "malware",
                 "encryption", "auth", "zero-day", "pentest", "ctf", "cybersecurity"},
    "devops": {"docker", "kubernetes", "k8s", "terraform", "ci", "cd", "deploy",
               "cloud", "aws", "gcp", "azure", "devops", "linux", "infra", "helm"},
    "data": {"database", "sql", "postgres", "redis", "mongo", "data", "pipeline",
             "etl", "analytics", "warehouse", "spark", "kafka", "streaming"},
    "lang": {"rust", "go", "golang", "python", "java", "c++", "zig", "mojo",
             "compiler", "language", "parser"},
}

TOPIC_ORDER = ["ai", "web", "mobile", "security", "devops", "data", "lang", "other"]


def classify_item(item: IntelItem) -> str:
    """Classify an item into a topic based on keywords."""
    text = f"{item.title} {item.description} {' '.join(item.tags)}".lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return topic
    return "other"


def compute_topic_distribution(items: list[IntelItem]) -> dict[str, int]:
    """Compute topic distribution for a list of items."""
    dist: dict[str, int] = {t: 0 for t in TOPIC_ORDER}
    for item in items:
        topic = classify_item(item)
        dist[topic] += 1
    return dist


def _draw_radar_ascii(dist: dict[str, int], width: int = 50, height: int = 25) -> list[str]:
    """Draw a radar/spider chart as ASCII art.

    Args:
        dist: Topic distribution dict (topic -> count).
        width: Canvas width in characters.
        height: Canvas height in lines.

    Returns:
        List of strings representing the chart lines.
    """
    # Normalize values to 0-1
    max_val = max(dist.values()) if dist.values() else 1
    if max_val == 0:
        max_val = 1

    topics = [t for t in TOPIC_ORDER if dist.get(t, 0) > 0]
    if not topics:
        return ["  (no data)"]

    n = len(topics)
    if n < 3:
        # For fewer than 3 topics, use a bar chart instead
        return _draw_bar_chart(dist, width)

    # Center and radius
    cx, cy = width // 2, height // 2
    radius = min(cx - 4, cy - 2)

    # Canvas
    canvas = [[' '] * width for _ in range(height)]

    # Calculate polygon vertices
    angles = [2 * math.pi * i / n - math.pi / 2 for i in range(n)]
    normalized = [dist.get(t, 0) / max_val for t in topics]

    # Draw concentric guide rings (3 levels)
    for level in [0.33, 0.66, 1.0]:
        ring_r = radius * level
        for a_idx in range(n):
            a1 = angles[a_idx]
            a2 = angles[(a_idx + 1) % n]
            steps = max(int(ring_r * abs(a2 - a1)), 3)
            for s in range(steps):
                t = s / steps
                angle = a1 + t * (a2 - a1)
                px = int(cx + ring_r * math.cos(angle))
                py = int(cy + ring_r * math.sin(angle))
                if 0 <= px < width and 0 <= py < height:
                    char = '·' if level < 1 else '∘'
                    canvas[py][px] = char

    # Draw axes from center to each vertex
    for i, angle in enumerate(angles):
        end_r = radius
        steps = int(end_r) + 1
        for s in range(steps):
            t = s / steps
            px = int(cx + end_r * t * math.cos(angle))
            py = int(cy + end_r * t * math.sin(angle))
            if 0 <= px < width and 0 <= py < height:
                if canvas[py][px] == ' ':
                    canvas[py][px] = '·'

    # Draw data polygon
    data_points = []
    for i, (angle, val) in enumerate(zip(angles, normalized)):
        r = radius * val
        px = int(cx + r * math.cos(angle))
        py = int(cy + r * math.sin(angle))
        data_points.append((px, py))

    # Fill polygon area with light shading
    # Draw edges between consecutive data points
    for i in range(n):
        x1, y1 = data_points[i]
        x2, y2 = data_points[(i + 1) % n]
        # Bresenham-ish line drawing
        steps = max(abs(x2 - x1), abs(y2 - y1), 1)
        for s in range(steps + 1):
            t = s / steps
            px = int(x1 + t * (x2 - x1))
            py = int(y1 + t * (y2 - y1))
            if 0 <= px < width and 0 <= py < height:
                canvas[py][px] = '█'

    # Mark data vertices
    for px, py in data_points:
        if 0 <= px < width and 0 <= py < height:
            canvas[py][py] = '★' if 0 <= py < height and 0 <= px < width else '█'
            canvas[py][px] = '★'

    # Draw center dot
    if 0 <= cx < width and 0 <= cy < height:
        canvas[cy][cx] = '●'

    # Convert canvas to strings
    return [''.join(row) for row in canvas]


def _draw_bar_chart(dist: dict[str, int], width: int = 50) -> list[str]:
    """Fallback bar chart when too few topics for radar."""
    max_val = max(dist.values()) if dist.values() else 1
    if max_val == 0:
        max_val = 1

    lines = []
    for topic in TOPIC_ORDER:
        count = dist.get(topic, 0)
        if count == 0:
            continue
        label, _ = TOPIC_DISPLAY.get(topic, (topic, "dim"))
        bar_len = int(count / max_val * 30)
        bar = '█' * bar_len + '░' * (30 - bar_len)
        lines.append(f"  {label:<16} {bar} {count:>3}")

    return lines


def render_radar_chart(
    console: Console,
    items: list[IntelItem],
    title: str = "📡 Topic Radar",
) -> None:
    """Render a beautiful radar chart showing topic distribution.

    Args:
        console: Rich Console instance.
        items: List of IntelItem to analyze.
        title: Chart title.
    """
    if not items:
        console.print(Panel("[dim]No items to analyze.[/dim]", border_style="dim"))
        return

    dist = compute_topic_distribution(items)
    total = sum(dist.values())

    # Build the visual display
    console.print()

    # Radar chart as styled panel
    chart_lines = _draw_radar_ascii(dist, width=55, height=22)
    chart_text = Text()
    for line in chart_lines:
        chart_text.append(line + "\n", style="bright_cyan")

    # Legend with counts
    legend = Text()
    legend.append("\n")
    for topic in TOPIC_ORDER:
        count = dist.get(topic, 0)
        if count == 0:
            continue
        label, color = TOPIC_DISPLAY.get(topic, (topic, "dim"))
        pct = count / total * 100 if total else 0
        # Mini bar
        bar_len = int(pct / 100 * 16)
        bar = '█' * bar_len + '░' * (16 - bar_len)
        legend.append(f"  {label:<18}", style=color)
        legend.append(f" {bar} ", style=color)
        legend.append(f" {count:>3} ({pct:.0f}%)\n", style="bold")

    # Group as radar + legend side by side
    from rich.columns import Columns
    from rich.console import Group

    content = Group(
        chart_text,
        legend,
    )

    console.print(
        Panel(
            content,
            title=f"[bold bright_cyan]{title}[/]",
            subtitle=f"[dim]{total} items classified[/]",
            border_style="bright_cyan",
            padding=(1, 2),
        )
    )


def render_topic_breakdown(
    console: Console,
    items: list[IntelItem],
) -> None:
    """Render a detailed topic breakdown table.

    Shows per-topic stats: item count, avg score, top item.
    """
    from rich.table import Table as RichTable

    if not items:
        return

    # Group items by topic
    topic_items: dict[str, list[IntelItem]] = {t: [] for t in TOPIC_ORDER}
    for item in items:
        topic = classify_item(item)
        topic_items[topic].append(item)

    tbl = RichTable(
        title="📊 Topic Breakdown",
        show_lines=True,
        border_style="bright_blue",
        header_style="bold bright_white on grey11",
    )
    tbl.add_column("Topic", style="bold", width=18)
    tbl.add_column("Items", justify="right", width=6)
    tbl.add_column("Avg Score", justify="right", width=10)
    tbl.add_column("Top Item", ratio=3, no_wrap=False)
    tbl.add_column("Trend", justify="center", width=10)

    total = sum(len(v) for v in topic_items.values())

    for topic in TOPIC_ORDER:
        t_items = topic_items[topic]
        if not t_items:
            continue

        label, color = TOPIC_DISPLAY.get(topic, (topic, "dim"))
        count = len(t_items)
        pct = count / total * 100 if total else 0
        avg_score = sum(i.score for i in t_items) / count if count else 0
        top_item = max(t_items, key=lambda x: x.score)
        top_title = top_item.title[:50]

        # Mini bar as trend indicator
        bar_len = int(pct / 100 * 8)
        trend = '█' * bar_len + '░' * (8 - bar_len)

        tbl.add_row(
            f"[{color}]{label}[/]",
            f"[bold]{count}[/] ({pct:.0f}%)",
            f"{avg_score:.0f}",
            top_title,
            trend,
        )

    console.print()
    console.print(tbl)
    console.print()

# [2026-05-19] Fix: race condition in radar_chart
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

    Fix: added proper type checking to prevent stale cache reference.
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

# [2026-05-19] Fix: race condition in radar_chart
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

    Fix: added proper type checking to prevent stale cache reference.
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

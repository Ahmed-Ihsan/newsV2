"""Rich terminal renderer for Trend Radar — stunning visual output.

This module is responsible for the 'wow factor' that earns stars.
Every output should look like a premium dashboard.
"""

import json
import math
from typing import Optional

from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.emoji import Emoji
from rich.markup import escape
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from .models import IntelItem, SourceType, TrendSnapshot


SOURCE_EMOJI = {
    SourceType.GITHUB: "🐙",
    SourceType.HACKERNEWS: "🔶",
    SourceType.REDDIT: "🤖",
    SourceType.ARXIV: "📄",
    SourceType.RSS: "📡",
    SourceType.PRODUCTHUNT: "🚀",
    SourceType.YOUTUBE: "▶️",
    SourceType.DEVTO: "👩‍💻",
    SourceType.LOBSTERS: "🦞",
    SourceType.MEDIUM: "✍️",
    SourceType.NEWS: "📰",
}

SOURCE_COLORS = {
    SourceType.GITHUB: "bright_white on grey11",
    SourceType.HACKERNEWS: "bold bright_yellow",
    SourceType.REDDIT: "bold bright_red",
    SourceType.ARXIV: "bold bright_cyan",
    SourceType.RSS: "bold bright_magenta",
    SourceType.PRODUCTHUNT: "bold bright_green",
    SourceType.YOUTUBE: "bold red",
    SourceType.DEVTO: "bold bright_white",
    SourceType.LOBSTERS: "bold dark_red",
    SourceType.MEDIUM: "bold bright_green",
    SourceType.NEWS: "bold bright_blue",
}

SOURCE_BORDER = {
    SourceType.GITHUB: "bright_white",
    SourceType.HACKERNEWS: "yellow",
    SourceType.REDDIT: "red",
    SourceType.ARXIV: "cyan",
    SourceType.RSS: "magenta",
    SourceType.PRODUCTHUNT: "green",
    SourceType.YOUTUBE: "red",
    SourceType.DEVTO: "white",
    SourceType.LOBSTERS: "dark_red",
    SourceType.MEDIUM: "green",
    SourceType.NEWS: "blue",
}

# Score tier styles
SCORE_TIERS = [
    (10000, "bold bright_red", "🔥"),
    (5000, "bold bright_red", "🔴"),
    (1000, "bold bright_yellow", "🟡"),
    (500, "bright_green", "🟢"),
    (100, "bright_cyan", "🔵"),
    (0, "dim", "⚪"),
]

BANNER_ART = r"""[bold bright_cyan]
  ████████╗██████╗ ███████╗███╗   ██╗██████╗     ██████╗  █████╗ ██████╗  █████╗ ██████╗ 
  ╚══██╔══╝██╔══██╗██╔════╝████╗  ██║██╔══██╗    ██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔══██╗
     ██║   ██████╔╝█████╗  ██╔██╗ ██║██║  ██║    ██████╔╝███████║██║  ██║███████║██████╔╝
     ██║   ██╔══██╗██╔══╝  ██║╚██╗██║██║  ██║    ██╔══██╗██╔══██║██║  ██║██╔══██║██╔══██╗
     ██║   ██║  ██║███████╗██║ ╚████║██████╔╝    ██║  ██║██║  ██║██████╔╝██║  ██║██║  ██║
     ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═════╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
[/bold bright_cyan][dim]  Multi-source tech intelligence · GitHub · HN · Reddit · arXiv · RSS · Product Hunt[/dim]"""


def sparkline(values: list[int], width: int = 20) -> str:
    """Generate a Unicode sparkline from a list of values."""
    if not values or max(values) == 0:
        return "─" * width

    blocks = " ▁▂▃▄▅▆▇█"
    mn, mx = min(values), max(values)
    rng = mx - mn or 1

    # Sample values to fit width
    if len(values) > width:
        step = len(values) / width
        sampled = [values[int(i * step)] for i in range(width)]
    else:
        sampled = values + [0] * (width - len(values))

    return "".join(blocks[min(int((v - mn) / rng * 8), 8)] for v in sampled)


def progress_bar(value: int, max_val: int, width: int = 20) -> str:
    """Generate a colored progress bar string."""
    if max_val <= 0:
        return "░" * width
    filled = min(int(value / max_val * width), width)
    return "█" * filled + "░" * (width - filled)


def gradient_bar(value: int, max_val: int, width: int = 20) -> Text:
    """Generate a gradient progress bar using Rich Text with colors."""
    if max_val <= 0:
        return Text("░" * width, style="dim")
    filled = min(int(value / max_val * width), width)
    t = Text()
    if filled > 0:
        t.append("█" * filled, style="bright_cyan")
    if width - filled > 0:
        t.append("░" * (width - filled), style="dim")
    return t


def score_badge(item: IntelItem) -> Text:
    """Return a score with a colored tier badge."""
    display = item.score_display
    for threshold, style, badge in SCORE_TIERS:
        if item.score >= threshold:
            return Text(f"{badge} {display}", style=style)
    return Text(f"⚪ {display}", style="dim")


def mini_sparkline(values: list[int], width: int = 8) -> str:
    """Generate a compact sparkline for inline use."""
    return sparkline(values, width)


class TerminalRenderer:
    """Renders trend data as rich terminal output — the wow factor."""

    def __init__(self, console: Optional[Console] = None, show_banner: bool = True):
        self.console = console or Console()
        self.show_banner = show_banner

    def render_snapshot(self, snapshot: TrendSnapshot, layout: str = "table", show_banner: bool = True) -> None:
        """Render a trend snapshot with full visual flair."""
        if self.show_banner:
            self.console.print(BANNER_ART)

        self._render_header(snapshot)

        if layout == "table":
            self._render_table(snapshot)
        elif layout == "cards":
            self._render_cards(snapshot)
        elif layout == "compact":
            self._render_compact(snapshot)

        self._render_keywords(snapshot)
        self._render_summary(snapshot)

    def render_items(self, items: list[IntelItem], title: str = "Trending") -> None:
        """Render a list of items as a beautiful table."""
        if not items:
            self.console.print(
                Panel("[dim]No items found.[/dim]", border_style="dim")
            )
            return

        table = Table(
            title=f"[bold]{title}[/bold]",
            show_lines=False,
            expand=True,
            border_style="bright_blue",
            title_style="bold bright_cyan",
            header_style="bold bright_white on grey11",
        )
        table.add_column("#", style="dim", width=3, justify="right")
        table.add_column("", width=3)
        table.add_column("Title", style="cyan", ratio=3, no_wrap=False)
        table.add_column("Score", justify="right", width=10)
        table.add_column("Details", ratio=2, style="dim", no_wrap=False)

        for i, item in enumerate(items, 1):
            emoji = SOURCE_EMOJI.get(item.source, "•")
            info = item.description[:60] + "…" if len(item.description) > 60 else item.description
            if item.repo_language:
                info = f"[bright_green]{item.repo_language}[/] {info}"

            # Score badge with tier icon
            score_text = score_badge(item)

            table.add_row(str(i), emoji, item.title, score_text, info)

        self.console.print()
        self.console.print(table)

    def _render_header(self, snapshot: TrendSnapshot):
        """Render a stunning dashboard header."""
        ts = snapshot.timestamp.strftime("%Y-%m-%d %H:%M UTC")

        header_table = Table.grid(padding=1)
        header_table.add_column(ratio=1)
        header_table.add_row(
            f"[bold bright_cyan]📡 Trend Radar[/]  [dim]·[/]  [bright_white]{ts}[/]"
        )

        # Source badges
        source_badges = []
        for src_name in snapshot.sources_queried:
            try:
                src_type = SourceType(src_name)
                emoji = SOURCE_EMOJI.get(src_type, "•")
            except ValueError:
                emoji = "•"
            badge = f"{emoji} {src_name}"
            source_badges.append(badge)

        badges_text = "  ".join(source_badges) if source_badges else "none"

        self.console.print()
        self.console.print(
            Panel(
                Group(
                    Align.center(header_table),
                    Align.center(
                        Text.from_markup(
                            f"[dim]Sources:[/] {badges_text}  [dim]│[/]  "
                            f"[dim]Items:[/] [bold]{snapshot.item_count}[/]"
                        )
                    ),
                ),
                border_style="bright_cyan",
                padding=(0, 2),
            )
        )

    def _render_table(self, snapshot: TrendSnapshot):
        """Render items grouped by source in colored tables."""
        any_items = False

        for source in SourceType:
            items = snapshot.by_source(source)
            if not items:
                continue

            any_items = True
            emoji = SOURCE_EMOJI.get(source, "•")
            border = SOURCE_BORDER.get(source, "dim")

            # Sort by score descending
            items_sorted = sorted(items, key=lambda x: x.score, reverse=True)

            table = Table(
                show_lines=False,
                expand=True,
                border_style=border,
                header_style=f"bold {border}",
                title_justify="left",
                padding=(0, 1),
            )
            table.add_column("#", style="dim", width=3, justify="right")
            table.add_column("Title", style="bright_white", ratio=3, no_wrap=False)
            table.add_column("Score", justify="right", width=12)
            table.add_column("Details", ratio=2, style="dim", no_wrap=False)

            max_score = max((it.score for it in items_sorted), default=1) or 1

            for i, item in enumerate(items_sorted[:10], 1):
                score_text = score_badge(item)

                # Build detail string
                details_parts = []
                if item.author:
                    details_parts.append(f"[bright_cyan]{item.author}[/]")
                if item.description:
                    desc = item.description[:50] + "…" if len(item.description) > 50 else item.description
                    details_parts.append(desc)
                details = "  ".join(details_parts)

                table.add_row(str(i), item.title, score_text, details)

            self.console.print()
            self.console.print(
                Panel(
                    table,
                    title=f"[bold]{emoji} {source.value.upper()}[/]",
                    title_align="left",
                    border_style=border,
                    padding=(0, 0),
                )
            )

        if not any_items:
            self.console.print(Panel("[dim]No items found from any source.[/dim]", border_style="dim"))

    def _render_cards(self, snapshot: TrendSnapshot):
        """Render items as panels/cards with enhanced visuals."""
        for i, item in enumerate(snapshot.top(12), 1):
            emoji = SOURCE_EMOJI.get(item.source, "•")
            border = SOURCE_BORDER.get(item.source, "dim")

            # Title with rank badge
            rank_badge = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
            title = Text(f" {rank_badge} {emoji} {item.title} ", style="bold bright_white")

            # Content
            content = Text()
            if item.description:
                content.append(item.description[:200] + "\n\n")
            if item.url:
                content.append(f"🔗 {item.url}\n", style="bright_blue underline")
            if item.author:
                content.append(f"👤 {item.author}", style="dim")
            if item.repo_language:
                content.append(f"  ·  💻 {item.repo_language}", style="bright_green")

            # Subtitle with score badge
            score_b = score_badge(item)
            subtitle = Text()
            subtitle.append_text(score_b)

            self.console.print(
                Panel(
                    content,
                    title=title,
                    subtitle=subtitle,
                    subtitle_align="right",
                    border_style=border,
                    padding=(0, 2),
                )
            )

    def _render_compact(self, snapshot: TrendSnapshot):
        """Render compact single-line items with sparkline bars."""
        items = snapshot.top(40)
        if not items:
            return
        max_score = max((it.score for it in items), default=1) or 1

        self.console.print()
        for i, item in enumerate(items, 1):
            emoji = SOURCE_EMOJI.get(item.source, "•")
            title = item.title[:55]
            bar = progress_bar(item.score, max_score, width=8)

            score_display = item.score_display
            rank_color = "bright_white" if i <= 3 else "bright_cyan" if i <= 10 else "dim"

            # Tier icon
            _, _, tier_icon = next(
                (t for t in SCORE_TIERS if item.score >= t[0]), (0, "dim", "⚪")
            )

            self.console.print(
                f"  [{rank_color}]{i:>2}.[/{rank_color}] {tier_icon} {emoji} {title:<58} "
                f"{bar} [{rank_color}]{score_display:>7}[/{rank_color}]"
            )

    def _render_keywords(self, snapshot: TrendSnapshot):
        """Render trending keywords as a beautiful tag cloud with bars."""
        kw = snapshot.keywords(20)
        if not kw:
            return

        self.console.print()
        self.console.print(Rule("[bold]🔑 Trending Keywords[/]", style="bright_blue"))

        # Build keyword display with frequency bars
        kw_table = Table(show_header=False, show_lines=False, padding=(0, 1), expand=True)
        kw_table.add_column("Word", style="bold", width=18)
        kw_table.add_column("Bar", ratio=2)
        kw_table.add_column("Count", justify="right", width=5)

        max_count = max(c for _, c in kw) if kw else 1
        for word, count in kw[:15]:
            bar = gradient_bar(count, max_count, width=25)
            if count >= 5:
                style = "bright_red"
            elif count >= 3:
                style = "bright_yellow"
            else:
                style = "dim"

            kw_table.add_row(
                f"[{style}]{word}[/{style}]",
                bar,
                f"[{style}]{count}[/{style}]",
            )

        self.console.print(kw_table)

    def _render_summary(self, snapshot: TrendSnapshot):
        """Render summary statistics with visual flair."""
        by_source = {}
        for item in snapshot.items:
            src = item.source.value
            by_source[src] = by_source.get(src, 0) + 1

        parts = []
        for src_name, count in sorted(by_source.items()):
            try:
                src_type = SourceType(src_name)
                emoji = SOURCE_EMOJI.get(src_type, "•")
            except ValueError:
                emoji = "•"
            parts.append(f"{emoji} {src_name}({count})")

        summary_line = "  │  ".join(parts)

        # Calculate avg score
        scores = [it.score for it in snapshot.items if it.score > 0]
        avg_score = sum(scores) / len(scores) if scores else 0

        self.console.print()
        self.console.print(Rule(style="dim"))
        self.console.print(
            f"  📊 [bold]{snapshot.item_count}[/] items  │  {summary_line}  │  "
            f"Avg score: [bold]{avg_score:.0f}[/]",
            style="dim",
        )

        if snapshot.errors:
            self.console.print(
                f"  ⚠️  [red]{len(snapshot.errors)} error(s)[/red]: "
                + "; ".join(snapshot.errors[:3]),
            )

        self.console.print()

    def render_source_distribution(self, snapshot: TrendSnapshot) -> None:
        """Render a visual source distribution chart — pie-style bar chart."""
        by_source: dict[str, int] = {}
        for item in snapshot.items:
            src = item.source.value
            by_source[src] = by_source.get(src, 0) + 1

        if not by_source:
            return

        self.console.print()
        self.console.print(Rule("[bold]📊 Source Distribution[/]", style="bright_blue"))

        # ASCII art pie chart
        total = sum(by_source.values())
        colors = {
            "github": "bright_white",
            "hackernews": "yellow",
            "reddit": "red",
            "arxiv": "cyan",
            "rss": "magenta",
            "producthunt": "green",
            "youtube": "red",
            "devto": "white",
            "lobsters": "dark_red",
            "medium": "green",
            "news": "blue",
        }
        emojis = {
            "github": "🐙",
            "hackernews": "🔶",
            "reddit": "🤖",
            "arxiv": "📄",
            "rss": "📡",
            "producthunt": "🚀",
            "youtube": "▶️",
            "devto": "👩‍💻",
            "lobsters": "🦞",
            "medium": "✍️",
            "news": "📰",
        }

        dist_table = Table(show_header=False, show_lines=False, padding=(0, 1), expand=True)
        dist_table.add_column("Source", width=18)
        dist_table.add_column("Bar", ratio=2)
        dist_table.add_column("Count", width=8, justify="right")
        dist_table.add_column("Percent", width=8, justify="right")

        max_count = max(by_source.values())
        for src_name in [s.value for s in SourceType]:
            count = by_source.get(src_name, 0)
            if count == 0:
                continue
            emoji = emojis.get(src_name, "•")
            color = colors.get(src_name, "dim")
            pct = count / total * 100

            # Gradient bar
            bar_width = 30
            filled = int(count / max_count * bar_width)
            bar = Text()
            bar.append("█" * filled, style=f"bold {color}")
            bar.append("░" * (bar_width - filled), style="dim")

            dist_table.add_row(
                f"{emoji} [{color}]{src_name}[/]",
                bar,
                f"[bold]{count}[/]",
                f"[dim]{pct:.0f}%[/]",
            )

        self.console.print(Panel(dist_table, border_style="bright_blue", padding=(0, 1)))

    def render_keyword_trends(self, keyword_data: list[tuple[str, list[int], int]]) -> None:
        """Render keyword trends with sparklines over time.

        Args:
            keyword_data: List of (keyword, historical_counts, current_count)
        """
        if not keyword_data:
            return

        self.console.print()
        self.console.print(Rule("[bold]📈 Keyword Trends (Sparklines)[/]", style="bright_blue"))

        tbl = Table(show_header=False, show_lines=False, padding=(0, 1), expand=True)
        tbl.add_column("Keyword", style="bold", width=16)
        tbl.add_column("Trend", width=20)
        tbl.add_column("Current", width=8, justify="right")
        tbl.add_column("Direction", width=8)

        for word, history, current in keyword_data:
            spark = sparkline(history, width=16)

            # Direction indicator
            if len(history) >= 2:
                if history[-1] > history[-2]:
                    direction = "[green]↑[/]"
                elif history[-1] < history[-2]:
                    direction = "[red]↓[/]"
                else:
                    direction = "[dim]→[/]"
            else:
                direction = "[dim]—[/]"

            style = "bright_red" if current >= 5 else "bright_yellow" if current >= 3 else "bright_white"
            tbl.add_row(
                f"[{style}]{word}[/]",
                f"[bright_cyan]{spark}[/]",
                f"[bold]{current}[/]",
                direction,
            )

        self.console.print(tbl)

    def render_diff(self, diff_data: dict) -> None:
        """Render a trend diff showing rising, falling, new, and gone items."""
        self.console.print()

        # Header
        current_ts = diff_data.get("current_ts", "")[:19]
        previous_ts = diff_data.get("previous_ts", "")[:19]
        current_count = diff_data.get("current_count", 0)
        previous_count = diff_data.get("previous_count", 0)

        self.console.print(
            Panel(
                f"[bold bright_cyan]📊 Trend Diff[/]\n"
                f"[dim]Previous:[/] {previous_ts} ({previous_count} items) → "
                f"[dim]Current:[/] {current_ts} ({current_count} items)",
                border_style="bright_cyan",
                padding=(0, 2),
            )
        )

        # Rising items
        rising = diff_data.get("rising", [])
        if rising:
            self.console.print()
            table = Table(
                show_lines=False, expand=True, border_style="green",
                header_style="bold green",
            )
            table.add_column("#", style="dim", width=3, justify="right")
            table.add_column("Title", style="bright_white", ratio=3)
            table.add_column("Source", style="dim", width=12)
            table.add_column("Score", justify="right", width=10)
            table.add_column("Change", justify="right", width=10)

            for i, item in enumerate(rising[:15], 1):
                delta = item.get("score_delta", 0)
                table.add_row(
                    str(i),
                    item.get("title", ""),
                    item.get("source", ""),
                    str(item.get("score", 0)),
                    f"[bold green]+{delta:,}[/]" if delta > 0 else str(delta),
                )
            self.console.print(Panel(table, title="[bold green]🔺 Rising[/]", border_style="green", padding=(0, 0)))

        # Falling items
        falling = diff_data.get("falling", [])
        if falling:
            self.console.print()
            table = Table(
                show_lines=False, expand=True, border_style="red",
                header_style="bold red",
            )
            table.add_column("#", style="dim", width=3, justify="right")
            table.add_column("Title", style="bright_white", ratio=3)
            table.add_column("Source", style="dim", width=12)
            table.add_column("Score", justify="right", width=10)
            table.add_column("Change", justify="right", width=10)

            for i, item in enumerate(falling[:15], 1):
                delta = item.get("score_delta", 0)
                table.add_row(
                    str(i),
                    item.get("title", ""),
                    item.get("source", ""),
                    str(item.get("score", 0)),
                    f"[bold red]{delta:,}[/]" if delta < 0 else str(delta),
                )
            self.console.print(Panel(table, title="[bold red]🔻 Falling[/]", border_style="red", padding=(0, 0)))

        # New items
        new_items = diff_data.get("new", [])
        if new_items:
            self.console.print()
            table = Table(
                show_lines=False, expand=True, border_style="cyan",
                header_style="bold cyan",
            )
            table.add_column("#", style="dim", width=3, justify="right")
            table.add_column("Title", style="bright_white", ratio=3)
            table.add_column("Source", style="dim", width=12)
            table.add_column("Score", justify="right", width=10)

            for i, item in enumerate(new_items[:10], 1):
                table.add_row(
                    str(i),
                    item.get("title", ""),
                    item.get("source", ""),
                    str(item.get("score", 0)),
                )
            self.console.print(Panel(table, title="[bold cyan]🆕 New[/]", border_style="cyan", padding=(0, 0)))

        # Gone items
        gone = diff_data.get("gone", [])
        if gone:
            self.console.print()
            self.console.print(f"  [dim]💨 {len(gone)} items dropped from previous snapshot[/dim]")

        if not rising and not falling and not new_items:
            self.console.print("[dim]No changes detected or insufficient history. Run 'trend-radar fetch' twice to build history.[/dim]")

        self.console.print()

    def render_health(self, health_data: dict[str, dict]) -> None:
        """Render source health check results."""
        self.console.print()
        table = Table(
            title="🏥 Source Health Check",
            show_lines=False,
            border_style="bright_blue",
            header_style="bold bright_white on grey11",
        )
        table.add_column("", width=3)
        table.add_column("Source", style="bold", width=15)
        table.add_column("Status", justify="center", width=12)
        table.add_column("Latency", justify="right", width=10)
        table.add_column("Items", justify="right", width=8)
        table.add_column("Error", style="dim", ratio=2)

        for name, info in sorted(health_data.items()):
            try:
                src_type = SourceType(name)
                emoji = SOURCE_EMOJI.get(src_type, "•")
            except ValueError:
                emoji = "•"

            status = info.get("status", "unknown")
            if status == "ok":
                status_text = "[green]✓ OK[/]"
            elif status == "empty":
                status_text = "[yellow]⚠ Empty[/]"
            elif status == "disabled":
                status_text = "[dim]⊘ Off[/]"
            else:
                status_text = "[red]✗ Error[/]"

            latency = info.get("latency_ms", 0)
            latency_text = f"{latency}ms"
            if latency > 5000:
                latency_text = f"[red]{latency}ms[/]"
            elif latency > 2000:
                latency_text = f"[yellow]{latency}ms[/]"

            items_count = info.get("items_fetched", 0)
            error = info.get("error", "") or ""

            table.add_row(emoji, name, status_text, latency_text, str(items_count), error[:60])

        self.console.print(table)
        self.console.print()


class JsonRenderer:
    """Renders trend data as JSON."""

    def render(self, snapshot: TrendSnapshot) -> str:
        data = {
            "timestamp": snapshot.timestamp.isoformat(),
            "sources": snapshot.sources_queried,
            "item_count": snapshot.item_count,
            "errors": snapshot.errors,
            "items": [item.to_dict() for item in snapshot.items],
            "keywords": snapshot.keywords(20),
        }
        return json.dumps(data, indent=2, ensure_ascii=False)


class MarkdownRenderer:
    """Renders trend data as Markdown."""

    def render(self, snapshot: TrendSnapshot) -> str:
        ts = snapshot.timestamp.strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            f"# 📡 Trend Radar — {ts}",
            "",
            f"> {snapshot.item_count} items from {', '.join(snapshot.sources_queried)}",
            "",
        ]

        for source in SourceType:
            items = snapshot.by_source(source)
            if not items:
                continue

            emoji = SOURCE_EMOJI.get(source, "•")
            lines.append(f"## {emoji} {source.value.upper()}")
            lines.append("")

            for i, item in enumerate(items[:10], 1):
                score_str = f" (⭐{item.score_display})" if item.score else ""
                lines.append(f"{i}. **[{item.title}]({item.url})**{score_str}")
                if item.description:
                    lines.append(f"   {item.description[:150]}")
                lines.append("")

        # Keywords
        kw = snapshot.keywords(15)
        if kw:
            lines.append("## 🔑 Trending Keywords")
            lines.append("")
            lines.append(", ".join(f"**{w}**({c})" for w, c in kw))
            lines.append("")

        return "\n".join(lines)

# [2026-04-23] Refactor: simplified render logic
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

# [2026-05-25] deduplication engine
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

# [2026-04-23] Refactor: simplified render logic
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

# [2026-05-25] deduplication engine
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

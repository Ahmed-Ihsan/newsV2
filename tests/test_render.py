"""Tests for the terminal renderer."""

from io import StringIO

from rich.console import Console

from trend_radar.models import IntelItem, SourceType, TrendSnapshot
from trend_radar.render import (
    TerminalRenderer,
    JsonRenderer,
    MarkdownRenderer,
    sparkline,
    progress_bar,
    gradient_bar,
    score_badge,
    SOURCE_EMOJI,
)


def _make_snapshot() -> TrendSnapshot:
    return TrendSnapshot(
        items=[
            IntelItem(title="test/repo", source=SourceType.GITHUB, score=500, author="user", description="A test repo"),
            IntelItem(title="Show HN: Something", source=SourceType.HACKERNEWS, score=300),
            IntelItem(title="AI paper", source=SourceType.ARXIV, score=0, description="A research paper"),
            IntelItem(title="Reddit post", source=SourceType.REDDIT, score=150),
            IntelItem(title="Product Launch", source=SourceType.PRODUCTHUNT, score=100),
            IntelItem(title="RSS Feed Item", source=SourceType.RSS, score=0),
        ],
        sources_queried=["github", "hackernews", "arxiv", "reddit", "producthunt", "rss"],
    )


def _get_output(renderer: TerminalRenderer, snapshot: TrendSnapshot, layout="table") -> str:
    buf = StringIO()
    console = Console(file=buf, width=120, force_terminal=True)
    renderer.console = console
    renderer.render_snapshot(snapshot, layout=layout)
    return buf.getvalue()


def test_render_table_layout():
    snap = _make_snapshot()
    r = TerminalRenderer(show_banner=False)
    out = _get_output(r, snap, "table")
    assert "GITHUB" in out
    assert "HACKERNEWS" in out
    assert "test/repo" in out
    assert "500" in out


def test_render_cards_layout():
    snap = _make_snapshot()
    r = TerminalRenderer(show_banner=False)
    out = _get_output(r, snap, "cards")
    assert "test/repo" in out
    assert "Show HN" in out


def test_render_compact_layout():
    snap = _make_snapshot()
    r = TerminalRenderer(show_banner=False)
    out = _get_output(r, snap, "compact")
    assert "test/repo" in out


def test_render_empty_snapshot():
    snap = TrendSnapshot()
    r = TerminalRenderer(show_banner=False)
    out = _get_output(r, snap)
    assert "No items" in out or "0" in out


def test_render_items():
    items = [
        IntelItem(title="item1", source=SourceType.GITHUB, score=100, description="desc1"),
        IntelItem(title="item2", source=SourceType.HACKERNEWS, score=50),
    ]
    buf = StringIO()
    console = Console(file=buf, width=120, force_terminal=True)
    r = TerminalRenderer(console=console, show_banner=False)
    r.render_items(items, title="Test Items")
    out = buf.getvalue()
    assert "item1" in out
    assert "item2" in out
    assert "Test Items" in out


def test_render_items_empty():
    buf = StringIO()
    console = Console(file=buf, width=120, force_terminal=True)
    r = TerminalRenderer(console=console, show_banner=False)
    r.render_items([], title="Empty")
    out = buf.getvalue()
    assert "No items" in out


def test_json_renderer():
    snap = _make_snapshot()
    r = JsonRenderer()
    out = r.render(snap)
    import json
    data = json.loads(out)
    assert data["item_count"] == 6
    assert len(data["items"]) == 6
    assert "github" in data["sources"]


def test_markdown_renderer():
    snap = _make_snapshot()
    r = MarkdownRenderer()
    out = r.render(snap)
    assert "# 📡 Trend Radar" in out
    assert "GITHUB" in out
    assert "test/repo" in out
    assert "Trending Keywords" in out


def test_sparkline():
    result = sparkline([1, 2, 3, 4, 5], width=5)
    assert len(result) == 5
    assert result[-1] == "█"  # max value


def test_sparkline_empty():
    result = sparkline([], width=5)
    assert result == "─" * 5


def test_sparkline_all_zero():
    result = sparkline([0, 0, 0], width=5)
    assert result == "─" * 5


def test_progress_bar():
    bar = progress_bar(50, 100, width=10)
    assert bar.count("█") == 5
    assert bar.count("░") == 5


def test_progress_bar_full():
    bar = progress_bar(100, 100, width=10)
    assert "░" not in bar


def test_progress_bar_zero():
    bar = progress_bar(0, 100, width=10)
    assert "█" not in bar


def test_source_emoji_coverage():
    for st in SourceType:
        assert st in SOURCE_EMOJI


def test_colored_score():
    """Test score_badge function with different score tiers."""
    high = IntelItem(title="a", source=SourceType.GITHUB, score=10000)
    mid = IntelItem(title="b", source=SourceType.GITHUB, score=2000)
    low = IntelItem(title="c", source=SourceType.GITHUB, score=50)
    zero = IntelItem(title="d", source=SourceType.GITHUB, score=0)

    # Just ensure no errors and return Text objects
    result_high = score_badge(high)
    result_mid = score_badge(mid)
    result_low = score_badge(low)
    result_zero = score_badge(zero)

    assert "10.0k" in str(result_high)
    assert "2.0k" in str(result_mid)
    assert "50" in str(result_low)
    assert "0" in str(result_zero)


def test_gradient_bar():
    """Test gradient bar generation."""
    from rich.text import Text
    result = gradient_bar(50, 100, width=10)
    assert isinstance(result, Text)


def test_score_badge_tiers():
    """Test score badge returns appropriate tier icons."""
    from trend_radar.render import SCORE_TIERS

    for threshold, style, badge in SCORE_TIERS:
        item = IntelItem(title="test", source=SourceType.GITHUB, score=threshold)
        result = score_badge(item)
        assert badge in str(result)

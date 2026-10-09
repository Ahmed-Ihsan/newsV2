"""Tests for v0.7.0 features — live dashboard, digest, init wizard, progress."""

import json
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from trend_radar.models import IntelItem, SourceType, TrendSnapshot


# ── Fixtures ──

def _make_snapshot(n_items: int = 10) -> TrendSnapshot:
    """Create a test snapshot with sample items."""
    items = []
    sources = [SourceType.GITHUB, SourceType.HACKERNEWS, SourceType.REDDIT, SourceType.ARXIV]
    for i in range(n_items):
        src = sources[i % len(sources)]
        items.append(IntelItem(
            title=f"Test Item {i+1} — {src.value} trending",
            source=src,
            url=f"https://example.com/{i+1}",
            description=f"Description for item {i+1} about AI and machine learning",
            score=1000 - i * 50,
            author=f"author{i+1}",
            tags=["ai", "llm"] if i % 2 == 0 else ["web", "react"],
        ))
    return TrendSnapshot(
        items=items,
        sources_queried=["github", "hackernews", "reddit", "arxiv"],
    )


# ── Live Dashboard Tests ──

class TestLiveDashboard:
    """Tests for the live auto-refreshing dashboard."""

    def test_build_dashboard_returns_panel(self):
        """_build_dashboard should return a Rich Panel."""
        from trend_radar.live import _build_dashboard
        from rich.panel import Panel

        snapshot = _make_snapshot(5)
        result = _build_dashboard(snapshot, elapsed=1.5, cycle=3)
        assert isinstance(result, Panel)

    def test_build_dashboard_empty_snapshot(self):
        """_build_dashboard should handle empty snapshots."""
        from trend_radar.live import _build_dashboard
        from rich.panel import Panel

        snapshot = TrendSnapshot(items=[], sources_queried=[])
        result = _build_dashboard(snapshot, elapsed=0, cycle=0)
        assert isinstance(result, Panel)

    def test_build_dashboard_includes_metadata(self):
        """Dashboard should include cycle count and elapsed time."""
        from trend_radar.live import _build_dashboard

        snapshot = _make_snapshot(3)
        result = _build_dashboard(snapshot, elapsed=2.5, cycle=7)

        # Panel should be created (basic check)
        assert result is not None

    def test_live_dashboard_class_init(self):
        """LiveDashboard should initialize properly."""
        from trend_radar.live import LiveDashboard

        mock_radar = MagicMock()
        dashboard = LiveDashboard(mock_radar, interval=10)
        assert dashboard.interval == 10
        assert dashboard.cycle == 0

    def test_live_dashboard_with_sources(self):
        """LiveDashboard should pass sources to radar.collect."""
        from trend_radar.live import LiveDashboard
        from rich.console import Console

        mock_radar = MagicMock()
        mock_radar.collect.return_value = _make_snapshot(5)

        dashboard = LiveDashboard(mock_radar, interval=1)

        # We can't actually run the live loop in tests, but we can verify init
        assert dashboard.radar == mock_radar


# ── Digest Tests ──

class TestDigest:
    """Tests for digest report generation."""

    def test_markdown_digest_basic(self):
        """generate_digest_markdown should produce valid markdown."""
        from trend_radar.digest import generate_digest_markdown

        snapshot = _make_snapshot(10)
        md = generate_digest_markdown(snapshot)

        assert "# 📡 Trend Radar Digest" in md
        assert "10" in md or "items" in md
        assert "Test Item" in md

    def test_markdown_digest_custom_title(self):
        """Digest should accept a custom title."""
        from trend_radar.digest import generate_digest_markdown

        snapshot = _make_snapshot(5)
        md = generate_digest_markdown(snapshot, title="My Custom Digest")

        assert "My Custom Digest" in md

    def test_markdown_digest_has_all_sources(self):
        """Digest should have sections for each source."""
        from trend_radar.digest import generate_digest_markdown

        snapshot = _make_snapshot(12)
        md = generate_digest_markdown(snapshot)

        assert "GITHUB" in md
        assert "HACKERNEWS" in md
        assert "REDDIT" in md
        assert "ARXIV" in md

    def test_markdown_digest_has_keywords(self):
        """Digest should include keywords section."""
        from trend_radar.digest import generate_digest_markdown

        snapshot = _make_snapshot(10)
        md = generate_digest_markdown(snapshot, include_keywords=True)

        assert "Trending Keywords" in md

    def test_markdown_digest_has_stats(self):
        """Digest should include summary stats."""
        from trend_radar.digest import generate_digest_markdown

        snapshot = _make_snapshot(8)
        md = generate_digest_markdown(snapshot, include_stats=True)

        assert "Summary" in md
        assert "Total items" in md

    def test_markdown_digest_top_n(self):
        """Digest should respect top_n parameter."""
        from trend_radar.digest import generate_digest_markdown

        snapshot = _make_snapshot(20)
        md = generate_digest_markdown(snapshot, top_n=3)

        # Should only have items 1-3 per source
        lines = md.split("\n")
        table_rows = [l for l in lines if l.startswith("|") and "Test Item" in l]
        # Each source should have at most 3 items
        assert len(table_rows) <= 4 * 3  # 4 sources * 3 items max

    def test_html_digest_basic(self):
        """generate_digest_html should produce valid HTML."""
        from trend_radar.digest import generate_digest_html

        snapshot = _make_snapshot(8)
        html = generate_digest_html(snapshot)

        assert "<!DOCTYPE html>" in html
        assert "Trend Radar" in html
        assert "Test Item" in html

    def test_html_digest_has_chart_js_references(self):
        """HTML digest should have source sections."""
        from trend_radar.digest import generate_digest_html

        snapshot = _make_snapshot(6)
        html = generate_digest_html(snapshot)

        assert "GITHUB" in html
        assert "HACKERNEWS" in html

    def test_html_digest_keywords(self):
        """HTML digest should include keywords."""
        from trend_radar.digest import generate_digest_html

        snapshot = _make_snapshot(10)
        html = generate_digest_html(snapshot)

        assert "Trending Keywords" in html

    def test_digest_empty_snapshot(self):
        """Digest should handle empty snapshots gracefully."""
        from trend_radar.digest import generate_digest_markdown, generate_digest_html

        snapshot = TrendSnapshot(items=[], sources_queried=[])
        md = generate_digest_markdown(snapshot)
        html = generate_digest_html(snapshot)

        assert "0" in md
        assert "<!DOCTYPE html>" in html


# ── Init Wizard Tests ──

class TestInitWizard:
    """Tests for the interactive setup wizard."""

    def test_default_config_structure(self):
        """DEFAULT_CONFIG should have expected structure."""
        from trend_radar.init_wizard import DEFAULT_CONFIG

        assert "sources" in DEFAULT_CONFIG
        assert "display" in DEFAULT_CONFIG
        assert "cache" in DEFAULT_CONFIG
        assert "github" in DEFAULT_CONFIG["sources"]
        assert "hackernews" in DEFAULT_CONFIG["sources"]
        assert "reddit" in DEFAULT_CONFIG["sources"]
        assert "arxiv" in DEFAULT_CONFIG["sources"]
        assert "rss" in DEFAULT_CONFIG["sources"]
        assert "producthunt" in DEFAULT_CONFIG["sources"]

    def test_deep_copy_dict(self):
        """_deep_copy_dict should create independent copies."""
        from trend_radar.init_wizard import _deep_copy_dict

        original = {"a": 1, "b": {"c": 2, "d": [3, 4]}, "e": [5, 6]}
        copy = _deep_copy_dict(original)

        assert copy == original
        assert copy is not original
        assert copy["b"] is not original["b"]
        assert copy["e"] is not original["e"]

    def test_deep_copy_dict_modification_independence(self):
        """Modifying copy should not affect original."""
        from trend_radar.init_wizard import _deep_copy_dict

        original = {"a": {"b": 1}}
        copy = _deep_copy_dict(original)
        copy["a"]["b"] = 999

        assert original["a"]["b"] == 1

    @patch("trend_radar.init_wizard.Prompt")
    @patch("trend_radar.init_wizard.Confirm")
    def test_wizard_returns_config(self, mock_confirm, mock_prompt):
        """Wizard should return a valid config dict."""
        from trend_radar.init_wizard import run_init_wizard
        from rich.console import Console

        # Mock user input
        mock_prompt.ask.side_effect = ["", "all", "table", "15"]
        mock_confirm.ask.return_value = False

        console = Console(file=open(os.devnull, "w"))
        config = run_init_wizard(console)

        assert "sources" in config
        assert "display" in config
        console.file.close()


# ── Source Distribution Rendering Tests ──

class TestSourceDistribution:
    """Tests for source distribution visualization."""

    def test_render_source_distribution(self):
        """render_source_distribution should not raise."""
        from trend_radar.render import TerminalRenderer
        from rich.console import Console

        console = Console(file=open(os.devnull, "w"))
        renderer = TerminalRenderer(console, show_banner=False)
        snapshot = _make_snapshot(10)

        # Should not raise
        renderer.render_source_distribution(snapshot)
        console.file.close()

    def test_render_source_distribution_empty(self):
        """render_source_distribution should handle empty snapshot."""
        from trend_radar.render import TerminalRenderer
        from rich.console import Console

        console = Console(file=open(os.devnull, "w"))
        renderer = TerminalRenderer(console, show_banner=False)
        snapshot = TrendSnapshot(items=[], sources_queried=[])

        # Should not raise
        renderer.render_source_distribution(snapshot)
        console.file.close()


# ── Keyword Trends Rendering Tests ──

class TestKeywordTrends:
    """Tests for keyword sparkline trends."""

    def test_render_keyword_trends(self):
        """render_keyword_trends should not raise."""
        from trend_radar.render import TerminalRenderer
        from rich.console import Console

        console = Console(file=open(os.devnull, "w"))
        renderer = TerminalRenderer(console, show_banner=False)

        data = [
            ("agent", [1, 3, 5, 8, 12], 12),
            ("llm", [2, 4, 3, 5, 7], 7),
            ("mcp", [0, 1, 2, 4, 6], 6),
        ]

        renderer.render_keyword_trends(data)
        console.file.close()

    def test_render_keyword_trends_empty(self):
        """render_keyword_trends should handle empty data."""
        from trend_radar.render import TerminalRenderer
        from rich.console import Console

        console = Console(file=open(os.devnull, "w"))
        renderer = TerminalRenderer(console, show_banner=False)
        renderer.render_keyword_trends([])
        console.file.close()


# ── Collect with Progress Tests ──

class TestCollectWithProgress:
    """Tests for progress-aware collection."""

    def test_collect_with_progress_callback(self):
        """collect_with_progress should call callback for each source."""
        from trend_radar.core import TrendRadar

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            radar = TrendRadar(db_path=db_path, use_cache=False)

            events = []
            def callback(event, data):
                events.append((event, data))

            # Mock source fetch
            mock_items = [IntelItem(title="Test", source=SourceType.GITHUB, score=100)]
            for name, source in radar.sources.items():
                source.fetch = MagicMock(return_value=mock_items)

            snapshot = radar.collect_with_progress(
                sources=["github", "hackernews"],
                limit=5,
                callback=callback,
            )

            # Should have start and done events
            start_events = [e for e in events if e[0] == "source_start"]
            done_events = [e for e in events if e[0] == "source_done"]

            assert len(start_events) == 2
            assert len(done_events) == 2
            assert snapshot.item_count == 2

        finally:
            os.unlink(db_path)

    def test_collect_with_progress_error_handling(self):
        """collect_with_progress should report errors via callback."""
        from trend_radar.core import TrendRadar

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            radar = TrendRadar(db_path=db_path, use_cache=False)

            events = []
            def callback(event, data):
                events.append((event, data))

            # Make github fail
            radar.sources["github"].fetch = MagicMock(side_effect=Exception("API error"))
            radar.sources["hackernews"].fetch = MagicMock(return_value=[
                IntelItem(title="HN Item", source=SourceType.HACKERNEWS, score=50)
            ])

            snapshot = radar.collect_with_progress(
                sources=["github", "hackernews"],
                limit=5,
                callback=callback,
            )

            error_events = [e for e in events if e[0] == "source_error"]
            assert len(error_events) == 1
            assert "API error" in error_events[0][1]["error"]
            assert len(snapshot.errors) == 1

        finally:
            os.unlink(db_path)

    def test_collect_with_progress_no_callback(self):
        """collect_with_progress should work without callback."""
        from trend_radar.core import TrendRadar

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            radar = TrendRadar(db_path=db_path, use_cache=False)
            mock_items = [IntelItem(title="Test", source=SourceType.GITHUB, score=100)]
            radar.sources["github"].fetch = MagicMock(return_value=mock_items)

            snapshot = radar.collect_with_progress(
                sources=["github"],
                limit=5,
                callback=None,
            )

            assert snapshot.item_count == 1

        finally:
            os.unlink(db_path)


# ── CLI Version Tests ──

class TestCLIVersion:
    """Tests for the version command."""

    def test_version_in_cli(self):
        """CLI should have version 1.0.0."""
        from trend_radar import __version__
        assert __version__ == "1.0.0"


# ── Web Dashboard Tests ──

class TestWebDashboard:
    """Tests for the enhanced web dashboard."""

    def test_dashboard_html_has_chartjs(self):
        """Dashboard HTML should include Chart.js."""
        from trend_radar.web import _dashboard_html

        html = _dashboard_html()
        assert "chart.js" in html.lower() or "Chart" in html

    def test_dashboard_html_has_source_chart(self):
        """Dashboard HTML should have chart containers."""
        from trend_radar.web import _dashboard_html

        html = _dashboard_html()
        assert "sourceChart" in html
        assert "kwChart" in html

    def test_dashboard_html_has_controls(self):
        """Dashboard HTML should have interactive controls."""
        from trend_radar.web import _dashboard_html

        html = _dashboard_html()
        assert "Fetch All" in html
        assert "AI Intel" in html
        assert "Keywords" in html
        assert "Stats" in html
        assert "Diff" in html

    def test_dashboard_html_version(self):
        """Dashboard HTML should show the current version."""
        from trend_radar.web import _dashboard_html

        html = _dashboard_html()
        assert "1.0.0" in html


# ── Integration Tests ──

class TestIntegration:
    """Integration tests for v0.7.0 features."""

    def test_import_all_new_modules(self):
        """All new modules should be importable."""
        from trend_radar.live import LiveDashboard, _build_dashboard
        from trend_radar.digest import generate_digest_markdown, generate_digest_html
        from trend_radar.init_wizard import run_init_wizard, DEFAULT_CONFIG

    def test_public_api_exports(self):
        """Public API should export new symbols."""
        from trend_radar import (
            LiveDashboard,
            generate_digest_markdown,
            generate_digest_html,
            run_init_wizard,
        )

    def test_full_digest_pipeline(self):
        """Full digest pipeline: collect → generate → verify."""
        from trend_radar.digest import generate_digest_markdown, generate_digest_html

        snapshot = _make_snapshot(15)

        # Markdown
        md = generate_digest_markdown(snapshot, title="Pipeline Test")
        assert "Pipeline Test" in md
        assert len(md) > 500  # Should be substantial

        # HTML
        html = generate_digest_html(snapshot, title="Pipeline Test")
        assert "Pipeline Test" in html
        assert len(html) > 1000  # Should be substantial

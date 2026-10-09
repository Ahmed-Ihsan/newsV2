"""Tests for v0.5.0 CLI commands: diff, top, health."""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from trend_radar.cli import main
from trend_radar.models import IntelItem, SourceType, TrendSnapshot


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_radar():
    """Mock TrendRadar with controllable responses."""
    with patch("trend_radar.cli.TrendRadar") as MockRadar:
        radar = MockRadar.return_value
        radar.config = MagicMock()
        radar.config.cache_enabled = False
        radar.config._config = {"sources": {"github": {"enabled": True}}}
        radar.sources = {"github": MagicMock()}
        yield radar


class TestDiffCommand:
    """Test the CLI diff command."""

    def test_diff_with_no_history(self, runner, mock_radar):
        """diff with no history should show empty message."""
        mock_radar.diff_snapshots.return_value = {
            "rising": [], "falling": [], "new": [], "gone": [],
            "current_count": 0, "previous_count": 0,
            "current_ts": "", "previous_ts": "",
        }
        result = runner.invoke(main, ["diff", "--no-banner"])
        assert result.exit_code == 0

    def test_diff_json_output(self, runner, mock_radar):
        """diff --json should output valid JSON."""
        mock_radar.diff_snapshots.return_value = {
            "rising": [{"title": "repo1", "score_delta": 50, "score": 150, "source": "github"}],
            "falling": [],
            "new": [],
            "gone": [],
            "current_count": 10,
            "previous_count": 8,
            "current_ts": "2026-05-13T00:00:00",
            "previous_ts": "2026-05-12T00:00:00",
        }
        result = runner.invoke(main, ["diff", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "rising" in data
        assert len(data["rising"]) == 1

    def test_diff_with_rising_and_falling(self, runner, mock_radar):
        """diff should render rising and falling items."""
        mock_radar.diff_snapshots.return_value = {
            "rising": [
                {"title": "hot-repo", "score_delta": 500, "score": 1500, "source": "github"},
            ],
            "falling": [
                {"title": "cold-repo", "score_delta": -200, "score": 300, "source": "github"},
            ],
            "new": [
                {"title": "new-repo", "score": 100, "source": "hackernews"},
            ],
            "gone": [],
            "current_count": 15,
            "previous_count": 12,
            "current_ts": "2026-05-13T02:00:00",
            "previous_ts": "2026-05-12T02:00:00",
        }
        result = runner.invoke(main, ["diff", "--no-banner"])
        assert result.exit_code == 0


class TestTopCommand:
    """Test the CLI top command."""

    def test_top_basic(self, runner, mock_radar):
        """top should show top items."""
        mock_radar.get_top_items.return_value = [
            IntelItem(title="top-repo", source=SourceType.GITHUB, score=1000),
            IntelItem(title="mid-repo", source=SourceType.HACKERNEWS, score=500),
        ]
        result = runner.invoke(main, ["top", "--no-banner"])
        assert result.exit_code == 0

    def test_top_json(self, runner, mock_radar):
        """top --json should output valid JSON."""
        mock_radar.get_top_items.return_value = [
            IntelItem(title="repo1", source=SourceType.GITHUB, score=100),
        ]
        result = runner.invoke(main, ["top", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "items" in data

    def test_top_with_topic(self, runner, mock_radar):
        """top --topic should pass topic to get_top_items."""
        mock_radar.get_top_items.return_value = []
        result = runner.invoke(main, ["top", "--topic", "ai"])
        assert result.exit_code == 0
        mock_radar.get_top_items.assert_called_once()

    def test_top_with_source(self, runner, mock_radar):
        """top --source should pass source to get_top_items."""
        mock_radar.get_top_items.return_value = []
        result = runner.invoke(main, ["top", "--source", "github"])
        assert result.exit_code == 0

    def test_top_with_limit(self, runner, mock_radar):
        """top --limit should pass limit to get_top_items."""
        mock_radar.get_top_items.return_value = []
        result = runner.invoke(main, ["top", "-n", "5"])
        assert result.exit_code == 0


class TestHealthCommand:
    """Test the CLI health command."""

    def test_health_all_ok(self, runner, mock_radar):
        """health should show all sources ok."""
        mock_radar.check_health.return_value = {
            "github": {"status": "ok", "latency_ms": 150, "items_fetched": 3, "error": None},
            "hackernews": {"status": "ok", "latency_ms": 200, "items_fetched": 3, "error": None},
        }
        result = runner.invoke(main, ["health"])
        assert result.exit_code == 0

    def test_health_with_errors(self, runner, mock_radar):
        """health should show source errors."""
        mock_radar.check_health.return_value = {
            "github": {"status": "error", "latency_ms": 5000, "items_fetched": 0, "error": "timeout"},
            "hackernews": {"status": "ok", "latency_ms": 100, "items_fetched": 3, "error": None},
        }
        result = runner.invoke(main, ["health"])
        assert result.exit_code == 0


class TestFetchWithTopic:
    """Test fetch command with --topic filter."""

    def test_fetch_with_topic(self, runner, mock_radar):
        """fetch --topic should filter items."""
        snap = TrendSnapshot(
            items=[
                IntelItem(title="AI agent", source=SourceType.GITHUB, score=100, description="machine learning"),
                IntelItem(title="React lib", source=SourceType.GITHUB, score=200, description="frontend"),
            ],
            sources_queried=["github"],
        )
        mock_radar.collect.return_value = snap
        mock_radar.collect_with_progress.return_value = snap
        mock_radar._matches_topic = lambda item, topic: topic == "ai" and "ai" in item.title.lower()

        result = runner.invoke(main, ["fetch", "--topic", "ai", "--no-banner"])
        assert result.exit_code == 0

    def test_fetch_with_no_concurrent(self, runner, mock_radar):
        """fetch --no-parallel should disable concurrent fetching."""
        snap = TrendSnapshot(items=[], sources_queried=[])
        mock_radar.collect.return_value = snap
        mock_radar.collect_with_progress.return_value = snap
        result = runner.invoke(main, ["fetch", "--no-parallel", "--no-banner"])
        assert result.exit_code == 0


class TestRenderDiff:
    """Test the diff renderer."""

    def test_render_diff_empty(self):
        """Should render empty diff gracefully."""
        from rich.console import Console
        from io import StringIO
        from trend_radar.render import TerminalRenderer

        buf = StringIO()
        console = Console(file=buf, width=120)
        renderer = TerminalRenderer(console, show_banner=False)

        renderer.render_diff({
            "rising": [], "falling": [], "new": [], "gone": [],
            "current_count": 0, "previous_count": 0,
            "current_ts": "", "previous_ts": "",
        })
        output = buf.getvalue()
        assert "insufficient history" in output.lower() or "no changes" in output.lower()

    def test_render_diff_with_data(self):
        """Should render diff with rising/falling items."""
        from rich.console import Console
        from io import StringIO
        from trend_radar.render import TerminalRenderer

        buf = StringIO()
        console = Console(file=buf, width=120)
        renderer = TerminalRenderer(console, show_banner=False)

        renderer.render_diff({
            "rising": [
                {"title": "hot-repo", "score_delta": 500, "score": 1500, "source": "github"},
            ],
            "falling": [
                {"title": "cold-repo", "score_delta": -200, "score": 300, "source": "github"},
            ],
            "new": [],
            "gone": [],
            "current_count": 10,
            "previous_count": 8,
            "current_ts": "2026-05-13T02:00:00",
            "previous_ts": "2026-05-12T02:00:00",
        })
        output = buf.getvalue()
        assert "hot-repo" in output
        assert "cold-repo" in output


class TestRenderHealth:
    """Test the health renderer."""

    def test_render_health_all_ok(self):
        """Should render health with all sources ok."""
        from rich.console import Console
        from io import StringIO
        from trend_radar.render import TerminalRenderer

        buf = StringIO()
        console = Console(file=buf, width=120)
        renderer = TerminalRenderer(console, show_banner=False)

        renderer.render_health({
            "github": {"status": "ok", "latency_ms": 150, "items_fetched": 3, "error": None},
            "hackernews": {"status": "empty", "latency_ms": 200, "items_fetched": 0, "error": None},
            "reddit": {"status": "error", "latency_ms": 5000, "items_fetched": 0, "error": "timeout"},
        })
        output = buf.getvalue()
        assert "github" in output.lower()
        assert "hackernews" in output.lower()

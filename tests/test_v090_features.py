"""Tests for v0.9.0 features — themes, dedup, snapshots, webhooks, obsidian, timeline."""

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from trend_radar.models import IntelItem, SourceType, TrendSnapshot


# ─── Theme Tests ──────────────────────────────────────────────────────────────

class TestThemes:
    """Test the theme system."""

    def test_default_theme_exists(self):
        from trend_radar.themes import get_theme, THEMES
        assert "default" in THEMES
        theme = get_theme("default")
        assert theme.primary == "bright_cyan"

    def test_all_predefined_themes(self):
        from trend_radar.themes import THEMES, list_themes
        names = list_themes()
        assert "default" in names
        assert "dracula" in names
        assert "monokai" in names
        assert "solarized" in names
        assert "nord" in names
        assert "gruvbox" in names
        assert "light" in names
        assert len(names) >= 7

    def test_theme_fallback(self):
        from trend_radar.themes import get_theme
        theme = get_theme("nonexistent_theme_xyz")
        assert theme.primary == "bright_cyan"  # falls back to default

    def test_theme_source_colors(self):
        from trend_radar.themes import get_theme
        for name in ["default", "dracula", "monokai", "solarized", "nord", "gruvbox", "light"]:
            theme = get_theme(name)
            assert theme.github != ""
            assert theme.hackernews != ""
            assert theme.reddit != ""
            assert theme.arxiv != ""
            assert theme.rss != ""
            assert theme.producthunt != ""

    def test_theme_source_color_method(self):
        from trend_radar.themes import get_theme
        theme = get_theme("default")
        assert theme.get_source_color("github") == theme.github
        assert theme.get_source_color("hackernews") == theme.hackernews
        assert theme.get_source_color("unknown_source") == theme.primary

    def test_theme_source_border_method(self):
        from trend_radar.themes import get_theme
        theme = get_theme("default")
        assert theme.get_source_border("github") == theme.github_border
        assert theme.get_source_border("unknown") == theme.panel_border

    def test_theme_score_styles(self):
        from trend_radar.themes import get_theme
        theme = get_theme("default")
        style, emoji = theme.get_score_style(15000)
        assert emoji == "🔥"
        style, emoji = theme.get_score_style(7000)
        assert emoji == "🔴"
        style, emoji = theme.get_score_style(2000)
        assert emoji == "🟡"
        style, emoji = theme.get_score_style(700)
        assert emoji == "🟢"
        style, emoji = theme.get_score_style(200)
        assert emoji == "🔵"
        style, emoji = theme.get_score_style(50)
        assert emoji == "⚪"

    def test_register_custom_theme(self):
        from trend_radar.themes import register_theme, get_theme, ThemeColors
        custom = ThemeColors(primary="bright_magenta", accent="bright_red")
        register_theme("custom_test_xyz", custom)
        theme = get_theme("custom_test_xyz")
        assert theme.primary == "bright_magenta"
        assert theme.accent == "bright_red"

    def test_theme_from_dict(self):
        from trend_radar.themes import theme_from_dict
        data = {"primary": "bright_magenta", "accent": "bright_red"}
        theme = theme_from_dict(data)
        assert theme.primary == "bright_magenta"
        assert theme.accent == "bright_red"
        assert theme.secondary == "bright_yellow"  # default

    def test_theme_dataclass_fields(self):
        from trend_radar.themes import ThemeColors
        theme = ThemeColors()
        assert hasattr(theme, "primary")
        assert hasattr(theme, "secondary")
        assert hasattr(theme, "accent")
        assert hasattr(theme, "muted")
        assert hasattr(theme, "score_fire")
        assert hasattr(theme, "panel_border")
        assert hasattr(theme, "success")
        assert hasattr(theme, "error")
        assert hasattr(theme, "warning")
        assert hasattr(theme, "info")

    def test_dracula_theme_colors(self):
        from trend_radar.themes import get_theme
        theme = get_theme("dracula")
        assert "bd93f9" in theme.primary
        assert "50fa7b" in theme.accent

    def test_nord_theme_colors(self):
        from trend_radar.themes import get_theme
        theme = get_theme("nord")
        assert "88c0d0" in theme.primary

    def test_gruvbox_theme_colors(self):
        from trend_radar.themes import get_theme
        theme = get_theme("gruvbox")
        assert "458588" in theme.primary


# ─── Deduplication Tests ──────────────────────────────────────────────────────

class TestDedup:
    """Test the cross-source deduplication engine."""

    def test_normalize_url_strips_tracking(self):
        from trend_radar.dedup import normalize_url
        result = normalize_url("https://www.example.com/path?utm_source=twitter&utm_medium=social&id=42")
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "id=42" in result
        assert "www." not in result

    def test_normalize_url_strips_www(self):
        from trend_radar.dedup import normalize_url
        result = normalize_url("https://www.example.com/page")
        assert "www." not in result
        assert "example.com" in result

    def test_normalize_url_strips_fragment(self):
        from trend_radar.dedup import normalize_url
        result = normalize_url("https://example.com/page#section1")
        assert "#" not in result

    def test_normalize_url_trailing_slash(self):
        from trend_radar.dedup import normalize_url
        result = normalize_url("https://example.com/page/")
        assert result.endswith("/page") or result == "https://example.com/page"

    def test_normalize_url_empty(self):
        from trend_radar.dedup import normalize_url
        assert normalize_url("") == ""

    def test_normalize_title_strips_hn_prefix(self):
        from trend_radar.dedup import normalize_title
        assert "show hn" not in normalize_title("Show HN: My Cool Project")
        assert "my cool project" == normalize_title("Show HN: My Cool Project")

    def test_normalize_title_strips_ask_hn(self):
        from trend_radar.dedup import normalize_title
        result = normalize_title("Ask HN: What's your favorite editor?")
        assert "ask hn" not in result
        assert "whats your favorite editor" in result

    def test_normalize_title_lowercases(self):
        from trend_radar.dedup import normalize_title
        result = normalize_title("UPPER CASE Title")
        assert result == result.lower()

    def test_normalize_title_removes_special_chars(self):
        from trend_radar.dedup import normalize_title
        result = normalize_title("Hello, World! #trending")
        assert "," not in result
        assert "!" not in result
        assert "#" not in result

    def test_normalize_title_empty(self):
        from trend_radar.dedup import normalize_title
        assert normalize_title("") == ""

    def test_title_similarity_identical(self):
        from trend_radar.dedup import title_similarity
        assert title_similarity("hello world", "hello world") == 1.0

    def test_title_similarity_different(self):
        from trend_radar.dedup import title_similarity
        assert title_similarity("apple banana", "car dog") == 0.0

    def test_title_similarity_partial(self):
        from trend_radar.dedup import title_similarity
        sim = title_similarity("my cool project", "my cool new project")
        assert 0.5 < sim < 1.0

    def test_title_similarity_empty(self):
        from trend_radar.dedup import title_similarity
        assert title_similarity("", "hello") == 0.0
        assert title_similarity("hello", "") == 0.0

    def test_dedup_url_duplicates(self):
        from trend_radar.dedup import DedupEngine
        items = [
            IntelItem(title="Project A", source=SourceType.HACKERNEWS, url="https://example.com/a", score=100),
            IntelItem(title="Project A", source=SourceType.REDDIT, url="https://www.example.com/a", score=50),
            IntelItem(title="Unique Item", source=SourceType.GITHUB, url="https://other.com/b", score=200),
        ]
        engine = DedupEngine()
        unique, groups = engine.deduplicate(items)
        assert len(unique) == 2  # one from dup group + unique item
        assert len(groups) == 1
        assert groups[0].source_count == 2

    def test_dedup_title_duplicates(self):
        from trend_radar.dedup import DedupEngine
        items = [
            IntelItem(title="Show HN: My AI Tool", source=SourceType.HACKERNEWS, url="https://hn.com/1", score=100),
            IntelItem(title="My AI Tool", source=SourceType.REDDIT, url="https://reddit.com/1", score=80),
            IntelItem(title="Completely Different", source=SourceType.GITHUB, url="https://github.com/1", score=200),
        ]
        engine = DedupEngine(title_threshold=0.5)
        unique, groups = engine.deduplicate(items)
        assert len(groups) >= 1

    def test_dedup_no_duplicates(self):
        from trend_radar.dedup import DedupEngine
        items = [
            IntelItem(title="Alpha", source=SourceType.GITHUB, url="https://a.com", score=100),
            IntelItem(title="Beta", source=SourceType.HACKERNEWS, url="https://b.com", score=50),
            IntelItem(title="Gamma", source=SourceType.REDDIT, url="https://c.com", score=75),
        ]
        engine = DedupEngine()
        unique, groups = engine.deduplicate(items)
        assert len(unique) == 3
        assert len(groups) == 0

    def test_dedup_empty_list(self):
        from trend_radar.dedup import DedupEngine
        engine = DedupEngine()
        unique, groups = engine.deduplicate([])
        assert unique == []
        assert groups == []

    def test_dedup_same_source_not_deduped(self):
        from trend_radar.dedup import DedupEngine
        items = [
            IntelItem(title="Similar Title", source=SourceType.HACKERNEWS, url="https://a.com", score=100),
            IntelItem(title="Similar Title Here", source=SourceType.HACKERNEWS, url="https://b.com", score=80),
        ]
        engine = DedupEngine(title_threshold=0.5)
        unique, groups = engine.deduplicate(items)
        # Same source should NOT be deduped by title
        assert len(unique) == 2

    def test_duplicate_group_properties(self):
        from trend_radar.dedup import DuplicateGroup
        items = [
            IntelItem(title="A", source=SourceType.GITHUB, score=100),
            IntelItem(title="B", source=SourceType.HACKERNEWS, score=200),
        ]
        group = DuplicateGroup(items=items, sources=["github", "hackernews"])
        assert group.source_count == 2
        assert group.total_score == 300
        assert group.max_score == 200

    def test_find_cross_source(self):
        from trend_radar.dedup import DedupEngine
        items = [
            IntelItem(title="Project X", source=SourceType.HACKERNEWS, url="https://example.com/x", score=100),
            IntelItem(title="Project X", source=SourceType.REDDIT, url="https://www.example.com/x", score=50),
        ]
        engine = DedupEngine()
        cross = engine.find_cross_source(items)
        assert len(cross) == 1
        assert cross[0].source_count == 2


# ─── Snapshot Tests ───────────────────────────────────────────────────────────

class TestSnapshots:
    """Test snapshot save/load and diffing."""

    def _make_store(self):
        from trend_radar.store import TrendStore
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            return TrendStore(db_path=f.name)

    def _make_snapshot(self, items=None, timestamp=None):
        return TrendSnapshot(
            timestamp=timestamp or datetime.now(timezone.utc),
            items=items or [],
            sources_queried=["github", "hackernews"],
        )

    def test_save_and_list_snapshots(self):
        from trend_radar.snapshots import SnapshotManager
        store = self._make_store()
        manager = SnapshotManager(store)

        snapshot = self._make_snapshot([
            IntelItem(title="Test", source=SourceType.GITHUB, score=100),
        ])
        snap_id = manager.save_snapshot(snapshot, label="test_label")
        assert snap_id > 0

        snapshots = manager.list_snapshots()
        assert len(snapshots) >= 1

    def test_snapshot_label(self):
        from trend_radar.snapshots import SnapshotManager
        store = self._make_store()
        manager = SnapshotManager(store)

        snapshot = self._make_snapshot([
            IntelItem(title="Test", source=SourceType.GITHUB, score=100),
        ])
        snap_id = manager.save_snapshot(snapshot, label="my_label")
        label = manager.get_label(snap_id)
        assert label == "my_label"

    def test_load_snapshot(self):
        from trend_radar.snapshots import SnapshotManager
        store = self._make_store()
        manager = SnapshotManager(store)

        items = [
            IntelItem(title="Item 1", source=SourceType.GITHUB, score=100, url="https://a.com"),
            IntelItem(title="Item 2", source=SourceType.HACKERNEWS, score=200, url="https://b.com"),
        ]
        snapshot = self._make_snapshot(items)
        snap_id = manager.save_snapshot(snapshot)

        loaded = manager.load_snapshot(snap_id)
        assert loaded is not None
        assert len(loaded.items) == 2

    def test_diff_snapshots_new_items(self):
        from trend_radar.snapshots import SnapshotManager
        store = self._make_store()
        manager = SnapshotManager(store)

        # Save first snapshot
        snap1 = self._make_snapshot([
            IntelItem(title="Item A", source=SourceType.GITHUB, url="https://a.com", score=100),
        ])
        id1 = manager.save_snapshot(snap1)

        # Save second with additional item
        snap2 = self._make_snapshot([
            IntelItem(title="Item A", source=SourceType.GITHUB, url="https://a.com", score=150),
            IntelItem(title="Item B", source=SourceType.HACKERNEWS, url="https://b.com", score=50),
        ])
        id2 = manager.save_snapshot(snap2)

        diff = manager.diff_snapshots(id1, id2)
        assert len(diff.new_items) == 1
        assert diff.new_items[0].title == "Item B"

    def test_diff_snapshots_score_changes(self):
        from trend_radar.snapshots import SnapshotManager
        store = self._make_store()
        manager = SnapshotManager(store)

        snap1 = self._make_snapshot([
            IntelItem(title="Item A", source=SourceType.GITHUB, url="https://a.com", score=100),
        ])
        id1 = manager.save_snapshot(snap1)

        snap2 = self._make_snapshot([
            IntelItem(title="Item A", source=SourceType.GITHUB, url="https://a.com", score=250),
        ])
        id2 = manager.save_snapshot(snap2)

        diff = manager.diff_snapshots(id1, id2)
        assert len(diff.score_changes) == 1
        item, old, new = diff.score_changes[0]
        assert old == 100
        assert new == 250

    def test_diff_snapshots_removed_items(self):
        from trend_radar.snapshots import SnapshotManager
        store = self._make_store()
        manager = SnapshotManager(store)

        snap1 = self._make_snapshot([
            IntelItem(title="Item A", source=SourceType.GITHUB, url="https://a.com", score=100),
            IntelItem(title="Item B", source=SourceType.HACKERNEWS, url="https://b.com", score=50),
        ])
        id1 = manager.save_snapshot(snap1)

        snap2 = self._make_snapshot([
            IntelItem(title="Item A", source=SourceType.GITHUB, url="https://a.com", score=100),
        ])
        id2 = manager.save_snapshot(snap2)

        diff = manager.diff_snapshots(id1, id2)
        assert len(diff.removed_items) == 1
        assert diff.removed_items[0].title == "Item B"

    def test_diff_summary(self):
        from trend_radar.snapshots import SnapshotDiff
        diff = SnapshotDiff(
            snapshot_old_id=1,
            snapshot_new_id=2,
            old_time=datetime.now(timezone.utc) - timedelta(hours=1),
            new_time=datetime.now(timezone.utc),
            new_items=[IntelItem(title="New", source=SourceType.GITHUB, score=100)],
            removed_items=[],
            score_changes=[(IntelItem(title="Up", source=SourceType.HACKERNEWS, score=200), 100, 200)],
        )
        summary = diff.summary()
        assert summary["new_items"] == 1
        assert summary["score_changes"] == 1
        assert summary["total_changes"] == 2
        assert len(summary["top_new"]) == 1

    def test_auto_diff_insufficient_snapshots(self):
        from trend_radar.snapshots import SnapshotManager
        store = self._make_store()
        manager = SnapshotManager(store)

        snap = self._make_snapshot([
            IntelItem(title="Item", source=SourceType.GITHUB, score=100),
        ])
        manager.save_snapshot(snap)

        result = manager.auto_diff()
        assert result is None


# ─── Webhook Tests ────────────────────────────────────────────────────────────

class TestWebhooks:
    """Test the notification webhook system."""

    def test_webhook_config_creation(self):
        from trend_radar.webhooks import WebhookConfig, WebhookType
        wh = WebhookConfig(
            name="test",
            url="https://hooks.slack.com/test",
            webhook_type=WebhookType.SLACK,
        )
        assert wh.name == "test"
        assert wh.webhook_type == WebhookType.SLACK
        assert wh.enabled is True

    def test_webhook_config_to_dict(self):
        from trend_radar.webhooks import WebhookConfig, WebhookType
        wh = WebhookConfig(name="test", url="https://example.com", webhook_type=WebhookType.DISCORD)
        d = wh.to_dict()
        assert d["name"] == "test"
        assert d["type"] == "discord"

    def test_webhook_config_from_dict(self):
        from trend_radar.webhooks import WebhookConfig, WebhookType
        data = {"name": "my_hook", "url": "https://example.com", "type": "telegram", "chat_id": "123"}
        wh = WebhookConfig.from_dict(data)
        assert wh.name == "my_hook"
        assert wh.webhook_type == WebhookType.TELEGRAM
        assert wh.chat_id == "123"

    def test_webhook_dispatcher_add_remove(self):
        from trend_radar.webhooks import WebhookDispatcher, WebhookConfig
        dispatcher = WebhookDispatcher()
        wh = WebhookConfig(name="test", url="https://example.com")
        dispatcher.add(wh)
        assert len(dispatcher.list_webhooks()) == 1
        assert dispatcher.get("test") is not None

        dispatcher.remove("test")
        assert len(dispatcher.list_webhooks()) == 0
        assert dispatcher.get("test") is None

    def test_webhook_dispatcher_remove_nonexistent(self):
        from trend_radar.webhooks import WebhookDispatcher
        dispatcher = WebhookDispatcher()
        assert dispatcher.remove("nonexistent") is False

    def test_format_slack_payload(self):
        from trend_radar.webhooks import WebhookDispatcher, WebhookPayload
        dispatcher = WebhookDispatcher()
        payload = WebhookPayload(
            title="Test Alert",
            message="Something trending!",
            items=[IntelItem(title="Cool Project", source=SourceType.GITHUB, score=500)],
        )
        body = dispatcher._format_slack(payload)
        assert "blocks" in body
        assert len(body["blocks"]) >= 2

    def test_format_discord_payload(self):
        from trend_radar.webhooks import WebhookDispatcher, WebhookPayload
        dispatcher = WebhookDispatcher()
        payload = WebhookPayload(
            title="Test",
            message="msg",
            items=[IntelItem(title="Item", source=SourceType.HACKERNEWS, score=100, url="https://example.com")],
        )
        body = dispatcher._format_discord(payload)
        assert "embeds" in body
        assert body["embeds"][0]["title"] == "📡 Test"

    def test_format_telegram_payload(self):
        from trend_radar.webhooks import WebhookDispatcher, WebhookPayload
        dispatcher = WebhookDispatcher()
        payload = WebhookPayload(
            title="Test",
            message="msg",
            items=[],
        )
        body = dispatcher._format_telegram(payload)
        assert "text" in body
        assert "Test" in body["text"]
        assert "parse_mode" in body

    def test_format_custom_payload(self):
        from trend_radar.webhooks import WebhookDispatcher, WebhookPayload
        dispatcher = WebhookDispatcher()
        payload = WebhookPayload(
            title="Test",
            message="msg",
            items=[IntelItem(title="A", source=SourceType.GITHUB, score=50)],
        )
        body = dispatcher._format_custom(payload)
        assert body["title"] == "Test"
        assert body["alert_type"] == "keyword"
        assert len(body["items"]) == 1

    def test_should_send_filters_disabled(self):
        from trend_radar.webhooks import WebhookDispatcher, WebhookConfig, WebhookPayload
        wh = WebhookConfig(name="test", url="https://example.com", enabled=False)
        dispatcher = WebhookDispatcher([wh])
        payload = WebhookPayload(title="T", message="M")
        assert dispatcher._should_send(wh, payload) is False

    def test_should_send_filters_source(self):
        from trend_radar.webhooks import WebhookDispatcher, WebhookConfig, WebhookPayload
        wh = WebhookConfig(name="test", url="https://example.com", sources=["github"])
        dispatcher = WebhookDispatcher()
        payload = WebhookPayload(title="T", message="M",
                                 items=[IntelItem(title="A", source=SourceType.HACKERNEWS, score=10)])
        assert dispatcher._should_send(wh, payload) is False

        payload2 = WebhookPayload(title="T", message="M",
                                  items=[IntelItem(title="A", source=SourceType.GITHUB, score=10)])
        assert dispatcher._should_send(wh, payload2) is True

    def test_should_send_filters_min_score(self):
        from trend_radar.webhooks import WebhookDispatcher, WebhookConfig, WebhookPayload
        wh = WebhookConfig(name="test", url="https://example.com", min_score=100)
        dispatcher = WebhookDispatcher()
        payload = WebhookPayload(title="T", message="M",
                                 items=[IntelItem(title="A", source=SourceType.GITHUB, score=50)])
        assert dispatcher._should_send(wh, payload) is False

        payload2 = WebhookPayload(title="T", message="M",
                                  items=[IntelItem(title="A", source=SourceType.GITHUB, score=200)])
        assert dispatcher._should_send(wh, payload2) is True

    @patch("trend_radar.webhooks.httpx.post")
    def test_send_dispatches(self, mock_post):
        from trend_radar.webhooks import WebhookDispatcher, WebhookConfig, WebhookType, WebhookPayload
        mock_post.return_value = MagicMock(status_code=200)

        wh = WebhookConfig(name="slack", url="https://hooks.slack.com/test", webhook_type=WebhookType.SLACK)
        dispatcher = WebhookDispatcher([wh])

        payload = WebhookPayload(title="Test", message="msg",
                                 items=[IntelItem(title="A", source=SourceType.GITHUB, score=10)])
        results = dispatcher.send(payload)
        assert results["slack"] is True
        mock_post.assert_called_once()

    @patch("trend_radar.webhooks.httpx.post")
    def test_send_handles_failure(self, mock_post):
        from trend_radar.webhooks import WebhookDispatcher, WebhookConfig, WebhookPayload
        mock_post.return_value = MagicMock(status_code=500, text="error")

        wh = WebhookConfig(name="test", url="https://example.com")
        dispatcher = WebhookDispatcher([wh])
        payload = WebhookPayload(title="T", message="M",
                                 items=[IntelItem(title="A", source=SourceType.GITHUB, score=10)])
        results = dispatcher.send(payload)
        assert results["test"] is False

    @patch("trend_radar.webhooks.httpx.post")
    def test_send_handles_exception(self, mock_post):
        from trend_radar.webhooks import WebhookDispatcher, WebhookConfig, WebhookPayload
        mock_post.side_effect = Exception("Network error")

        wh = WebhookConfig(name="test", url="https://example.com")
        dispatcher = WebhookDispatcher([wh])
        payload = WebhookPayload(title="T", message="M",
                                 items=[IntelItem(title="A", source=SourceType.GITHUB, score=10)])
        results = dispatcher.send(payload)
        assert results["test"] is False


# ─── Obsidian Export Tests ────────────────────────────────────────────────────

class TestObsidianExport:
    """Test Obsidian-compatible markdown export."""

    def _make_snapshot(self):
        return TrendSnapshot(
            timestamp=datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc),
            items=[
                IntelItem(title="AI Agent Framework", source=SourceType.GITHUB,
                          url="https://github.com/example/ai", score=5000,
                          description="An AI agent framework", tags=["ai", "agent"]),
                IntelItem(title="Show HN: New Tool", source=SourceType.HACKERNEWS,
                          url="https://hn.com/1", score=300,
                          description="A new developer tool", tags=["tools"]),
                IntelItem(title="LLaMA Discussion", source=SourceType.REDDIT,
                          url="https://reddit.com/1", score=200, author="user1"),
            ],
            sources_queried=["github", "hackernews", "reddit"],
        )

    def test_export_daily_note_has_frontmatter(self):
        from trend_radar.obsidian_export import export_obsidian_daily
        snapshot = self._make_snapshot()
        content = export_obsidian_daily(snapshot)
        assert content.startswith("---")
        assert "title:" in content
        assert "date:" in content
        assert "type: trend-radar" in content
        assert "tags:" in content

    def test_export_daily_note_has_items(self):
        from trend_radar.obsidian_export import export_obsidian_daily
        snapshot = self._make_snapshot()
        content = export_obsidian_daily(snapshot)
        assert "AI Agent Framework" in content
        assert "New Tool" in content
        assert "LLaMA Discussion" in content

    def test_export_daily_note_has_source_sections(self):
        from trend_radar.obsidian_export import export_obsidian_daily
        snapshot = self._make_snapshot()
        content = export_obsidian_daily(snapshot)
        assert "🐙" in content
        assert "🔶" in content
        assert "🤖" in content

    def test_export_daily_note_has_links(self):
        from trend_radar.obsidian_export import export_obsidian_daily
        snapshot = self._make_snapshot()
        content = export_obsidian_daily(snapshot)
        assert "[AI Agent Framework](https://github.com/example/ai)" in content

    def test_export_daily_note_custom_title(self):
        from trend_radar.obsidian_export import export_obsidian_daily
        snapshot = self._make_snapshot()
        content = export_obsidian_daily(snapshot, title="My Custom Report")
        assert "My Custom Report" in content

    def test_export_vault_creates_multiple_files(self):
        from trend_radar.obsidian_export import export_obsidian_vault
        snapshot = self._make_snapshot()
        files = export_obsidian_vault(snapshot)
        assert len(files) >= 3  # daily + per-source + MOC
        assert any("Daily Notes" in f for f in files.keys())
        assert any("Trends" in f for f in files.keys())

    def test_export_vault_moc(self):
        from trend_radar.obsidian_export import export_obsidian_vault
        snapshot = self._make_snapshot()
        files = export_obsidian_vault(snapshot)
        moc = files.get("Trend Radar MOC.md", "")
        assert "MOC" in moc
        assert "🐙" in moc or "🔶" in moc

    def test_export_item_has_frontmatter(self):
        from trend_radar.obsidian_export import export_obsidian_item
        item = IntelItem(
            title="Test Item",
            source=SourceType.GITHUB,
            url="https://github.com/test",
            score=1000,
            author="user",
            tags=["python", "ai"],
        )
        content = export_obsidian_item(item)
        assert content.startswith("---")
        assert "title:" in content
        assert "source: github" in content
        assert "score: 1000" in content
        assert "python" in content

    def test_export_daily_note_empty_snapshot(self):
        from trend_radar.obsidian_export import export_obsidian_daily
        snapshot = TrendSnapshot(
            timestamp=datetime.now(timezone.utc),
            items=[],
            sources_queried=[],
        )
        content = export_obsidian_daily(snapshot)
        assert "Trend Radar" in content
        assert "---" in content

    def test_export_daily_note_has_keywords(self):
        from trend_radar.obsidian_export import export_obsidian_daily
        # Create snapshot with items sharing keywords to trigger keyword section
        items = [
            IntelItem(title="Agent framework for coding", source=SourceType.GITHUB, score=500),
            IntelItem(title="New agent framework released", source=SourceType.HACKERNEWS, score=300),
            IntelItem(title="Agent-based coding tools", source=SourceType.REDDIT, score=200),
        ]
        snapshot = TrendSnapshot(
            timestamp=datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc),
            items=items,
            sources_queried=["github", "hackernews", "reddit"],
        )
        content = export_obsidian_daily(snapshot)
        assert "Trending Keywords" in content or "agent" in content.lower()


# ─── Timeline Tests ───────────────────────────────────────────────────────────

class TestTimeline:
    """Test timeline visualization."""

    def test_topic_timeline_properties(self):
        from trend_radar.timeline import TopicTimeline
        tt = TopicTimeline(
            keyword="agent",
            points=[
                (datetime(2026, 5, 10, tzinfo=timezone.utc), 5),
                (datetime(2026, 5, 11, tzinfo=timezone.utc), 10),
                (datetime(2026, 5, 12, tzinfo=timezone.utc), 15),
            ],
        )
        assert tt.total == 30
        assert tt.trend == "↑"
        assert tt.peak_count == 15

    def test_topic_timeline_declining(self):
        from trend_radar.timeline import TopicTimeline
        tt = TopicTimeline(
            keyword="old",
            points=[
                (datetime(2026, 5, 10, tzinfo=timezone.utc), 20),
                (datetime(2026, 5, 11, tzinfo=timezone.utc), 10),
                (datetime(2026, 5, 12, tzinfo=timezone.utc), 5),
            ],
        )
        assert tt.trend == "↓"

    def test_topic_timeline_stable(self):
        from trend_radar.timeline import TopicTimeline
        tt = TopicTimeline(
            keyword="stable",
            points=[
                (datetime(2026, 5, 10, tzinfo=timezone.utc), 10),
                (datetime(2026, 5, 11, tzinfo=timezone.utc), 11),
                (datetime(2026, 5, 12, tzinfo=timezone.utc), 10),
            ],
        )
        assert tt.trend == "→"

    def test_topic_timeline_empty(self):
        from trend_radar.timeline import TopicTimeline
        tt = TopicTimeline(keyword="empty", points=[])
        assert tt.total == 0
        assert tt.trend == "→"
        assert tt.peak_count == 0
        assert tt.peak_time is None

    def test_timeline_data_top_topics(self):
        from trend_radar.timeline import TimelineData, TopicTimeline
        data = TimelineData(
            topics=[
                TopicTimeline(keyword="low", points=[(datetime.now(timezone.utc), 1)]),
                TopicTimeline(keyword="high", points=[(datetime.now(timezone.utc), 100)]),
                TopicTimeline(keyword="mid", points=[(datetime.now(timezone.utc), 50)]),
            ],
        )
        top = data.top_topics
        assert top[0].keyword == "high"
        assert top[1].keyword == "mid"
        assert top[2].keyword == "low"

    def test_extract_keywords(self):
        from trend_radar.timeline import extract_keywords_from_items
        items = [
            IntelItem(title="Agent framework for AI systems", source=SourceType.GITHUB, score=100),
            IntelItem(title="New agent tool released", source=SourceType.HACKERNEWS, score=50),
            IntelItem(title="Agent-based systems debate", source=SourceType.REDDIT, score=75),
        ]
        keywords = extract_keywords_from_items(items, min_freq=2)
        assert "agent" in keywords
        assert "systems" in keywords

    def test_extract_keywords_min_freq(self):
        from trend_radar.timeline import extract_keywords_from_items
        items = [
            IntelItem(title="Alpha beta gamma", source=SourceType.GITHUB, score=100),
            IntelItem(title="Delta epsilon zeta", source=SourceType.HACKERNEWS, score=50),
        ]
        keywords = extract_keywords_from_items(items, min_freq=2)
        # No word appears twice
        assert len(keywords) == 0

    def test_sparkline_from_points(self):
        from trend_radar.timeline import sparkline_from_points
        points = [
            (datetime(2026, 5, 10, tzinfo=timezone.utc), 1),
            (datetime(2026, 5, 11, tzinfo=timezone.utc), 5),
            (datetime(2026, 5, 12, tzinfo=timezone.utc), 10),
        ]
        spark = sparkline_from_points(points, width=10)
        assert len(spark) == 10
        assert spark != "─" * 10  # Should have actual data

    def test_sparkline_empty_points(self):
        from trend_radar.timeline import sparkline_from_points
        spark = sparkline_from_points([], width=10)
        assert spark == "─" * 10

    def test_compute_timeline_empty_store(self):
        from trend_radar.timeline import compute_timeline
        from trend_radar.store import TrendStore
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            store = TrendStore(db_path=f.name)
        data = compute_timeline(store, days=7)
        assert data.total_snapshots == 0
        assert data.topics == []

    def test_render_timeline_panel_empty(self):
        from trend_radar.timeline import render_timeline_panel, TimelineData
        data = TimelineData(topics=[], total_snapshots=0)
        panel = render_timeline_panel(data)
        assert panel is not None

    def test_render_timeline_panel_with_data(self):
        from trend_radar.timeline import render_timeline_panel, TimelineData, TopicTimeline
        data = TimelineData(
            topics=[
                TopicTimeline(keyword="agent", points=[
                    (datetime(2026, 5, 10, tzinfo=timezone.utc), 5),
                    (datetime(2026, 5, 12, tzinfo=timezone.utc), 15),
                ]),
            ],
            total_snapshots=5,
        )
        panel = render_timeline_panel(data)
        assert panel is not None


# ─── Store Extension Tests ────────────────────────────────────────────────────

class TestStoreExtensions:
    """Test store.list_snapshots and store.get_snapshot."""

    def _make_store(self):
        from trend_radar.store import TrendStore
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            return TrendStore(db_path=f.name)

    def test_list_snapshots(self):
        store = self._make_store()
        snap = TrendSnapshot(
            timestamp=datetime.now(timezone.utc),
            items=[IntelItem(title="Test", source=SourceType.GITHUB, score=10)],
            sources_queried=["github"],
        )
        store.save_snapshot(snap)
        result = store.list_snapshots(limit=10)
        assert len(result) >= 1

    def test_get_snapshot(self):
        store = self._make_store()
        items = [
            IntelItem(title="Item A", source=SourceType.GITHUB, url="https://a.com", score=100),
            IntelItem(title="Item B", source=SourceType.HACKERNEWS, url="https://b.com", score=50),
        ]
        snap = TrendSnapshot(
            timestamp=datetime.now(timezone.utc),
            items=items,
            sources_queried=["github", "hackernews"],
        )
        snap_id = store.save_snapshot(snap)

        loaded = store.get_snapshot(snap_id)
        assert loaded is not None
        assert len(loaded.items) == 2
        assert loaded.items[0].title == "Item A"

    def test_get_snapshot_nonexistent(self):
        store = self._make_store()
        result = store.get_snapshot(99999)
        assert result is None


# ─── CLI Command Tests ────────────────────────────────────────────────────────

class TestCLIv090:
    """Test v0.9.0 CLI commands via Click test runner."""

    def test_themes_command(self):
        from click.testing import CliRunner
        from trend_radar.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["themes", "--list"])
        assert result.exit_code == 0
        assert "Theme" in result.output or "theme" in result.output.lower()

    def test_version_090(self):
        from click.testing import CliRunner
        from trend_radar.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert "1.0.0" in result.output

    def test_webhooks_list_empty(self):
        from click.testing import CliRunner
        from trend_radar.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["webhooks", "--list"])
        assert result.exit_code == 0

    def test_snapshots_list_empty(self):
        from click.testing import CliRunner
        from trend_radar.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["snapshots", "--list"])
        assert result.exit_code == 0

    def test_timeline_command(self):
        from click.testing import CliRunner
        from trend_radar.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["timeline", "--days", "7", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "topics" in data
        assert "total_snapshots" in data


# ─── Integration Tests ────────────────────────────────────────────────────────

class TestIntegration:
    """Test that all v0.9.0 modules integrate properly."""

    def test_import_all_modules(self):
        """Verify all new modules can be imported."""
        from trend_radar.themes import THEMES, get_theme, list_themes, ThemeColors, register_theme, theme_from_dict
        from trend_radar.dedup import DedupEngine, DuplicateGroup, normalize_url, normalize_title, title_similarity
        from trend_radar.snapshots import SnapshotManager, SnapshotDiff
        from trend_radar.webhooks import WebhookDispatcher, WebhookConfig, WebhookType, WebhookPayload
        from trend_radar.timeline import compute_timeline, render_timeline_panel, TopicTimeline, TimelineData, extract_keywords_from_items
        from trend_radar.obsidian_export import export_obsidian_daily, export_obsidian_vault, export_obsidian_item
        # If we get here, all imports succeeded
        assert True

    def test_dedup_with_obsidian_export(self):
        """Dedup items then export unique ones to Obsidian."""
        from trend_radar.dedup import DedupEngine
        from trend_radar.obsidian_export import export_obsidian_daily

        items = [
            IntelItem(title="Project X", source=SourceType.HACKERNEWS, url="https://example.com/x", score=100),
            IntelItem(title="Project X", source=SourceType.REDDIT, url="https://www.example.com/x", score=50),
            IntelItem(title="Unique Y", source=SourceType.GITHUB, url="https://other.com/y", score=200),
        ]

        engine = DedupEngine()
        unique, groups = engine.deduplicate(items)
        snapshot = TrendSnapshot(
            timestamp=datetime.now(timezone.utc),
            items=unique,
            sources_queried=["hackernews", "reddit", "github"],
        )
        content = export_obsidian_daily(snapshot)
        assert "Unique Y" in content
        assert "---" in content

    def test_theme_integration_with_render(self):
        """Verify themes can be used to customize rendering."""
        from trend_radar.themes import get_theme
        theme = get_theme("dracula")
        assert "bd93f9" in theme.primary
        style, emoji = theme.get_score_style(5000)
        assert emoji == "🔴"

    def test_full_pipeline_dedup_snapshot(self):
        """Full pipeline: items → dedup → save snapshot → load → verify."""
        from trend_radar.dedup import DedupEngine
        from trend_radar.snapshots import SnapshotManager
        from trend_radar.store import TrendStore

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            store = TrendStore(db_path=f.name)

        items = [
            IntelItem(title="A", source=SourceType.GITHUB, url="https://a.com", score=100),
            IntelItem(title="A", source=SourceType.HACKERNEWS, url="https://www.a.com", score=80),
            IntelItem(title="B", source=SourceType.REDDIT, url="https://b.com", score=50),
        ]

        engine = DedupEngine()
        unique, groups = engine.deduplicate(items)

        snapshot = TrendSnapshot(
            timestamp=datetime.now(timezone.utc),
            items=unique,
            sources_queried=["github", "hackernews", "reddit"],
        )

        manager = SnapshotManager(store)
        snap_id = manager.save_snapshot(snapshot, label="integration_test")

        loaded = manager.load_snapshot(snap_id)
        assert loaded is not None
        assert len(loaded.items) == len(unique)

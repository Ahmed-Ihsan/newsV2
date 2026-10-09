"""Tests for v0.6.0 features — normalization, momentum, alerts, OPML, async, retry."""

import json
import math
import os
import sqlite3
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Retry Module ──────────────────────────────────────────────────────

class TestRetryBackoff:
    def test_retry_success_first_try(self):
        from trend_radar.retry import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = succeed()
        assert result == "ok"
        assert call_count == 1

    def test_retry_success_after_failures(self):
        from trend_radar.retry import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01, retryable_exceptions=(ValueError,))
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "ok"

        result = flaky()
        assert result == "ok"
        assert call_count == 3

    def test_retry_exhausted_raises(self):
        from trend_radar.retry import retry_with_backoff

        @retry_with_backoff(max_retries=2, base_delay=0.01, retryable_exceptions=(ValueError,))
        def always_fail():
            raise ValueError("always fail")

        with pytest.raises(ValueError, match="always fail"):
            always_fail()

    def test_retry_on_retry_callback(self):
        from trend_radar.retry import retry_with_backoff

        retry_info = []

        @retry_with_backoff(
            max_retries=2, base_delay=0.01,
            retryable_exceptions=(ValueError,),
            on_retry=lambda n, e, d: retry_info.append((n, str(e), d)),
        )
        def flaky():
            if len(retry_info) < 2:
                raise ValueError("oops")
            return "ok"

        result = flaky()
        assert result == "ok"
        assert len(retry_info) == 2
        assert retry_info[0][0] == 1  # retry count

    def test_robust_client_creation(self):
        from trend_radar.retry import RobustHttpClient

        client = RobustHttpClient(timeout=10.0, max_retries=2)
        assert client.timeout == 10.0
        assert client.max_retries == 2


# ── Normalization Module ─────────────────────────────────────────────

class TestNormalization:
    def test_normalize_github_high_score(self):
        from trend_radar.normalization import normalize_score
        from trend_radar.models import IntelItem, SourceType

        item = IntelItem(title="test", source=SourceType.GITHUB, score=10000)
        norm = normalize_score(item)
        assert 80 <= norm <= 100  # High score should be high normalized

    def test_normalize_github_zero_score(self):
        from trend_radar.normalization import normalize_score
        from trend_radar.models import IntelItem, SourceType

        item = IntelItem(title="test", source=SourceType.GITHUB, score=0)
        assert normalize_score(item) == 0.0

    def test_normalize_hackernews(self):
        from trend_radar.normalization import normalize_score
        from trend_radar.models import IntelItem, SourceType

        item = IntelItem(title="test", source=SourceType.HACKERNEWS, score=500)
        norm = normalize_score(item)
        assert 50 <= norm <= 100

    def test_normalize_reddit(self):
        from trend_radar.normalization import normalize_score
        from trend_radar.models import IntelItem, SourceType

        item = IntelItem(title="test", source=SourceType.REDDIT, score=10000)
        norm = normalize_score(item)
        assert 50 <= norm <= 100

    def test_normalize_arxiv_binary(self):
        from trend_radar.normalization import normalize_score
        from trend_radar.models import IntelItem, SourceType

        item = IntelItem(title="test paper", source=SourceType.ARXIV, score=0)
        assert normalize_score(item) == 50.0  # Binary scoring

    def test_normalized_badge_tiers(self):
        from trend_radar.normalization import normalized_badge

        emoji, style = normalized_badge(95)
        assert emoji == "🔥"

        emoji, style = normalized_badge(80)
        assert emoji == "🔴"

        emoji, style = normalized_badge(60)
        assert emoji == "🟡"

        emoji, style = normalized_badge(30)
        assert emoji == "🟢"

        emoji, style = normalized_badge(5)
        assert emoji == "🔵"

        emoji, style = normalized_badge(0)
        assert emoji == "⚪"

    def test_rank_cross_source(self):
        from trend_radar.normalization import rank_cross_source
        from trend_radar.models import IntelItem, SourceType

        items = [
            IntelItem(title="low github", source=SourceType.GITHUB, score=100),
            IntelItem(title="high hn", source=SourceType.HACKERNEWS, score=800),
            IntelItem(title="mid reddit", source=SourceType.REDDIT, score=5000),
            IntelItem(title="arxiv paper", source=SourceType.ARXIV, score=0),
        ]
        ranked = rank_cross_source(items, top_n=4)
        assert len(ranked) == 4
        # All should have normalized_score in extra
        for item in ranked:
            assert "normalized_score" in item.extra

    def test_enrich_with_normalized(self):
        from trend_radar.normalization import enrich_with_normalized
        from trend_radar.models import IntelItem, SourceType

        items = [
            IntelItem(title="a", source=SourceType.GITHUB, score=5000),
            IntelItem(title="b", source=SourceType.REDDIT, score=1000),
        ]
        enrich_with_normalized(items)
        assert items[0].extra["normalized_score"] > 0
        assert items[1].extra["normalized_score"] > 0


# ── Momentum Module ──────────────────────────────────────────────────

class TestMomentum:
    def test_compute_momentum_rising(self):
        from trend_radar.momentum import compute_momentum

        m = compute_momentum(
            title="test", source="github",
            current_score=1000, previous_score=500,
            hours_between=24,
        )
        assert m.velocity > 0
        assert m.score_delta == 500
        assert m.trajectory in ("rising", "viral")

    def test_compute_momentum_falling(self):
        from trend_radar.momentum import compute_momentum

        m = compute_momentum(
            title="test", source="hackernews",
            current_score=100, previous_score=500,
            hours_between=24,
        )
        assert m.velocity < 0
        assert m.score_delta == -400
        assert m.trajectory == "falling"

    def test_compute_momentum_with_acceleration(self):
        from trend_radar.momentum import compute_momentum

        m = compute_momentum(
            title="test", source="github",
            current_score=3000, previous_score=1500,
            hours_between=24,
            earlier_score=500, earlier_hours=24,
        )
        assert m.acceleration > 0  # Accelerating
        assert m.confidence > 0.5

    def test_momentum_data_predicted_score(self):
        from trend_radar.momentum import MomentumData

        m = MomentumData(
            title="test", source="github",
            current_score=1000, velocity=50,
            trajectory="rising",
        )
        predicted = m.predicted_score_24h
        assert predicted > 1000  # Should predict growth

    def test_momentum_is_trending(self):
        from trend_radar.momentum import MomentumData

        m = MomentumData(title="t", source="s", velocity=100, trajectory="viral")
        assert m.is_trending

        m2 = MomentumData(title="t", source="s", velocity=-10, trajectory="falling")
        assert not m2.is_trending

    def test_classify_trajectory_viral(self):
        from trend_radar.momentum import classify_trajectory

        assert classify_trajectory(200, 50, 1000) == "viral"
        assert classify_trajectory(50, 0, 1000) == "rising"
        assert classify_trajectory(0, 0, 1000) == "stable"
        assert classify_trajectory(-50, 0, 1000) == "falling"
        assert classify_trajectory(0, 0, 0) == "dead"

    def test_momentum_to_dict(self):
        from trend_radar.momentum import MomentumData

        m = MomentumData(
            title="test", source="github",
            current_score=1000, previous_score=500,
            score_delta=500, velocity=20.83,
            trajectory="rising", confidence=0.8,
        )
        d = m.to_dict()
        assert d["title"] == "test"
        assert d["velocity"] == 20.83
        assert "predicted_24h" in d


# ── Alerts Module ────────────────────────────────────────────────────

class TestAlerts:
    def test_alert_store_add_and_list(self, tmp_path):
        from trend_radar.alerts import AlertStore

        db = str(tmp_path / "test_alerts.db")
        store = AlertStore(db_path=db)
        store.add_alert("llm", threshold=3)
        store.add_alert("rust", source_filter="github")

        alerts = store.list_alerts()
        assert len(alerts) == 2
        keywords = [a.keyword for a in alerts]
        assert "llm" in keywords
        assert "rust" in keywords

    def test_alert_store_remove(self, tmp_path):
        from trend_radar.alerts import AlertStore

        db = str(tmp_path / "test_alerts.db")
        store = AlertStore(db_path=db)
        store.add_alert("test")
        assert store.remove_alert("test")
        assert len(store.list_alerts()) == 0
        assert not store.remove_alert("nonexistent")

    def test_alert_check_matches(self, tmp_path):
        from trend_radar.alerts import AlertStore

        db = str(tmp_path / "test_alerts.db")
        store = AlertStore(db_path=db)
        store.add_alert("llm", threshold=1)

        items = [
            {"title": "New LLM Framework", "description": "A new LLM tool", "source": "github", "score": 100},
            {"title": "Rust compiler update", "description": "Nothing here", "source": "github", "score": 50},
        ]

        matches = store.check_alerts(items)
        assert len(matches) == 1
        assert matches[0].alert.keyword == "llm"
        assert matches[0].count == 1

    def test_alert_check_threshold(self, tmp_path):
        from trend_radar.alerts import AlertStore

        db = str(tmp_path / "test_alerts.db")
        store = AlertStore(db_path=db)
        store.add_alert("ai", threshold=3)

        items = [
            {"title": "AI tool 1", "description": "", "source": "github", "score": 10},
            {"title": "AI tool 2", "description": "", "source": "github", "score": 20},
        ]

        matches = store.check_alerts(items)
        assert len(matches) == 0  # threshold 3 not met

    def test_alert_source_filter(self, tmp_path):
        from trend_radar.alerts import AlertStore

        db = str(tmp_path / "test_alerts.db")
        store = AlertStore(db_path=db)
        store.add_alert("python", source_filter="github")

        items = [
            {"title": "Python framework", "source": "reddit", "score": 100},
            {"title": "Python library", "source": "github", "score": 200},
        ]

        matches = store.check_alerts(items)
        assert len(matches) == 1
        assert matches[0].matching_items[0]["source"] == "github"

    def test_alert_to_dict(self, tmp_path):
        from trend_radar.alerts import Alert

        a = Alert(keyword="test", threshold=5, source_filter="github")
        d = a.to_dict()
        assert d["keyword"] == "test"
        assert d["threshold"] == 5

    def test_alert_match_to_dict(self, tmp_path):
        from trend_radar.alerts import Alert, AlertMatch

        a = Alert(keyword="test")
        m = AlertMatch(alert=a, matching_items=[{"title": "x"}], count=1)
        d = m.to_dict()
        assert d["keyword"] == "test"
        assert d["count"] == 1


# ── OPML Module ──────────────────────────────────────────────────────

class TestOPML:
    def test_import_opml_valid(self, tmp_path):
        from trend_radar.opml import import_opml

        opml_content = """<?xml version="1.0"?>
        <opml version="2.0">
          <head><title>Test</title></head>
          <body>
            <outline text="Tech" title="Tech">
              <outline text="HN" title="Hacker News" xmlUrl="https://hnrss.org/frontpage" />
              <outline text="TC" title="TechCrunch" xmlUrl="https://techcrunch.com/feed/" />
            </outline>
          </body>
        </opml>"""

        opml_file = tmp_path / "test.opml"
        opml_file.write_text(opml_content)

        feeds = import_opml(str(opml_file))
        assert len(feeds) == 2
        assert "Hacker News" in feeds
        assert feeds["Hacker News"] == "https://hnrss.org/frontpage"

    def test_import_opml_not_found(self):
        from trend_radar.opml import import_opml
        with pytest.raises(FileNotFoundError):
            import_opml("/nonexistent/file.opml")

    def test_import_opml_invalid_xml(self, tmp_path):
        from trend_radar.opml import import_opml

        bad_file = tmp_path / "bad.opml"
        bad_file.write_text("<html>not opml</html>")

        with pytest.raises(ValueError, match="Not an OPML file"):
            import_opml(str(bad_file))

    def test_import_urls(self, tmp_path):
        from trend_radar.opml import import_urls

        url_file = tmp_path / "urls.txt"
        url_file.write_text("https://example.com/feed.xml\nhttps://blog.com/rss\n# comment\n")

        feeds = import_urls(str(url_file))
        assert len(feeds) == 2

    def test_import_json_dict_format(self, tmp_path):
        from trend_radar.opml import import_json

        json_file = tmp_path / "feeds.json"
        json_file.write_text(json.dumps({"feeds": {"HN": "https://hnrss.org/frontpage"}}))

        feeds = import_json(str(json_file))
        assert "HN" in feeds

    def test_import_json_list_format(self, tmp_path):
        from trend_radar.opml import import_json

        json_file = tmp_path / "feeds.json"
        json_file.write_text(json.dumps([
            {"name": "HN", "url": "https://hnrss.org/frontpage"},
            {"name": "TC", "url": "https://techcrunch.com/feed/"},
        ]))

        feeds = import_json(str(json_file))
        assert len(feeds) == 2

    def test_import_feeds_auto_detect(self, tmp_path):
        from trend_radar.opml import import_feeds

        opml_content = """<?xml version="1.0"?>
        <opml version="2.0">
          <head><title>Test</title></head>
          <body>
            <outline text="Feed" xmlUrl="https://example.com/rss" />
          </body>
        </opml>"""

        opml_file = tmp_path / "test.opml"
        opml_file.write_text(opml_content)

        feeds = import_feeds(str(opml_file))
        assert len(feeds) == 1


# ── Async Fetch Module ───────────────────────────────────────────────

class TestAsyncFetch:
    @pytest.mark.asyncio
    async def test_fetch_source_async(self):
        from trend_radar.async_fetch import fetch_source_async
        from trend_radar.models import IntelItem, SourceType

        mock_source = MagicMock()
        mock_source.name = "test"
        mock_source.fetch.return_value = [
            IntelItem(title="test item", source=SourceType.GITHUB, score=100),
        ]

        name, items, error = await fetch_source_async(mock_source, limit=5)
        assert name == "test"
        assert len(items) == 1
        assert error is None

    @pytest.mark.asyncio
    async def test_fetch_source_async_error(self):
        from trend_radar.async_fetch import fetch_source_async

        mock_source = MagicMock()
        mock_source.name = "broken"
        mock_source.fetch.side_effect = Exception("API down")

        name, items, error = await fetch_source_async(mock_source)
        assert name == "broken"
        assert len(items) == 0
        assert "API down" in error


# ── Integration: CLI New Commands ────────────────────────────────────

class TestCLINewCommands:
    def test_alert_add_command(self):
        from click.testing import CliRunner
        from trend_radar.cli import main

        runner = CliRunner()
        with runner.isolated_filesystem():
            os.environ["TREND_RADAR_HOME"] = os.getcwd() + "/.trend-radar"
            result = runner.invoke(main, ["alert-add", "llm", "--threshold", "3"])
            assert result.exit_code == 0
            assert "Alert added" in result.output

    def test_alert_list_command_empty(self):
        from click.testing import CliRunner
        from trend_radar.cli import main

        runner = CliRunner()
        with runner.isolated_filesystem():
            os.environ["TREND_RADAR_HOME"] = os.getcwd() + "/.trend-radar"
            result = runner.invoke(main, ["alert-list"])
            assert result.exit_code == 0
            assert "No alerts" in result.output

    def test_opml_import_command(self):
        from click.testing import CliRunner
        from trend_radar.cli import main

        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".trend-radar", exist_ok=True)
            os.environ["TREND_RADAR_HOME"] = os.getcwd() + "/.trend-radar"

            # Create test OPML
            with open("test.opml", "w") as f:
                f.write("""<?xml version="1.0"?>
                <opml version="2.0">
                  <head><title>Test</title></head>
                  <body>
                    <outline text="Feed1" xmlUrl="https://example.com/rss" />
                  </body>
                </opml>""")

            result = runner.invoke(main, ["opml-import", "test.opml"])
            assert result.exit_code == 0
            assert "Imported" in result.output

    @patch("trend_radar.core.TrendRadar.collect")
    def test_ranked_command(self, mock_collect):
        from click.testing import CliRunner
        from trend_radar.cli import main
        from trend_radar.models import IntelItem, SourceType, TrendSnapshot

        mock_collect.return_value = TrendSnapshot(
            items=[
                IntelItem(title="test", source=SourceType.GITHUB, score=1000),
            ],
            sources_queried=["github"],
        )

        runner = CliRunner()
        result = runner.invoke(main, ["ranked", "--no-banner"])
        assert result.exit_code == 0


# ── Integration: Web New Endpoints ───────────────────────────────────

class TestWebNewEndpoints:
    def test_momentum_endpoint(self, tmp_path):
        from fastapi.testclient import TestClient
        from trend_radar.web import create_app
        from trend_radar.core import TrendRadar

        db_path = str(tmp_path / "test.db")
        radar = TrendRadar(db_path=db_path)
        app = create_app(radar=radar)
        client = TestClient(app)

        resp = client.get("/api/momentum")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @patch("trend_radar.core.TrendRadar.collect")
    def test_ranked_endpoint(self, mock_collect, tmp_path):
        from fastapi.testclient import TestClient
        from trend_radar.web import create_app
        from trend_radar.core import TrendRadar
        from trend_radar.models import TrendSnapshot, IntelItem, SourceType

        mock_collect.return_value = TrendSnapshot(
            items=[IntelItem(title="test", source=SourceType.GITHUB, score=1000)],
            sources_queried=["github"],
        )

        db_path = str(tmp_path / "test.db")
        radar = TrendRadar(db_path=db_path)
        app = create_app(radar=radar)
        client = TestClient(app)

        resp = client.get("/api/ranked?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "items" in data

    def test_alerts_list_endpoint(self, tmp_path):
        from fastapi.testclient import TestClient
        from trend_radar.web import create_app
        from trend_radar.core import TrendRadar

        db_path = str(tmp_path / "test.db")
        radar = TrendRadar(db_path=db_path)
        app = create_app(radar=radar)
        client = TestClient(app)

        resp = client.get("/api/alerts")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_alerts_add_endpoint(self, tmp_path):
        from fastapi.testclient import TestClient
        from trend_radar.web import create_app
        from trend_radar.core import TrendRadar

        db_path = str(tmp_path / "test.db")
        radar = TrendRadar(db_path=db_path)
        app = create_app(radar=radar)
        client = TestClient(app)

        resp = client.post("/api/alerts/add?keyword=llm&threshold=3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["keyword"] == "llm"
        assert data["threshold"] == 3

    @patch("trend_radar.core.TrendRadar.collect")
    def test_alerts_check_endpoint(self, mock_collect, tmp_path):
        from fastapi.testclient import TestClient
        from trend_radar.web import create_app
        from trend_radar.core import TrendRadar
        from trend_radar.models import TrendSnapshot

        mock_collect.return_value = TrendSnapshot(items=[], sources_queried=[])

        db_path = str(tmp_path / "test.db")
        radar = TrendRadar(db_path=db_path)
        app = create_app(radar=radar)
        client = TestClient(app)

        resp = client.get("/api/alerts/check")
        assert resp.status_code == 200

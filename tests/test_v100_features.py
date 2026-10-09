"""Tests for v1.0.0 features — demo mode and doctor command."""

import pytest
from datetime import datetime, timezone

from trend_radar.demo import (
    generate_demo_snapshot,
    _gen_github,
    _gen_hn,
    _gen_reddit,
    _gen_arxiv,
    _gen_rss,
    _gen_producthunt,
)
from trend_radar.doctor import (
    run_doctor,
    DoctorReport,
    CheckResult,
    _check_python_version,
    _check_dependency,
    _check_config,
    _check_database,
)
from trend_radar.models import SourceType, TrendSnapshot


# ── Demo Tests ──────────────────────────────────────────────────────


class TestGenerateDemoSnapshot:
    """Tests for the demo data generator."""

    def test_basic_snapshot(self):
        """generate_demo_snapshot returns a valid TrendSnapshot."""
        snap = generate_demo_snapshot()
        assert isinstance(snap, TrendSnapshot)
        assert snap.item_count > 0
        assert len(snap.sources_queried) == 6
        assert snap.errors == []

    def test_with_seed_reproducible(self):
        """Same seed produces same results."""
        snap1 = generate_demo_snapshot(seed=42)
        snap2 = generate_demo_snapshot(seed=42)
        assert snap1.item_count == snap2.item_count
        assert snap1.items[0].title == snap2.items[0].title
        assert snap1.items[0].score == snap2.items[0].score

    def test_different_seeds_differ(self):
        """Different seeds produce different results."""
        snap1 = generate_demo_snapshot(seed=1)
        snap2 = generate_demo_snapshot(seed=999)
        # With 90 items, at least some should differ
        titles1 = {i.title for i in snap1.items}
        titles2 = {i.title for i in snap2.items}
        # They use random.sample so order differs
        assert snap1.items[0].title != snap2.items[0].title or snap1.items[1].title != snap2.items[1].title

    def test_limit_per_source(self):
        """Limit controls items per source."""
        snap = generate_demo_snapshot(limit=5)
        for src in SourceType:
            src_items = [i for i in snap.items if i.source == src]
            if src_items:  # source was included
                assert len(src_items) <= 5

    def test_single_source_github(self):
        """Can fetch only GitHub demo data."""
        snap = generate_demo_snapshot(sources=["github"], limit=5)
        assert all(i.source == SourceType.GITHUB for i in snap.items)
        assert len(snap.items) == 5

    def test_single_source_hn(self):
        """Can fetch only HN demo data."""
        snap = generate_demo_snapshot(sources=["hackernews"], limit=3)
        assert all(i.source == SourceType.HACKERNEWS for i in snap.items)

    def test_single_source_reddit(self):
        """Can fetch only Reddit demo data."""
        snap = generate_demo_snapshot(sources=["reddit"], limit=4)
        assert all(i.source == SourceType.REDDIT for i in snap.items)

    def test_single_source_arxiv(self):
        """Can fetch only arXiv demo data."""
        snap = generate_demo_snapshot(sources=["arxiv"], limit=5)
        assert all(i.source == SourceType.ARXIV for i in snap.items)

    def test_single_source_rss(self):
        """Can fetch only RSS demo data."""
        snap = generate_demo_snapshot(sources=["rss"], limit=3)
        assert all(i.source == SourceType.RSS for i in snap.items)

    def test_single_source_ph(self):
        """Can fetch only Product Hunt demo data."""
        snap = generate_demo_snapshot(sources=["producthunt"], limit=3)
        assert all(i.source == SourceType.PRODUCTHUNT for i in snap.items)

    def test_hn_alias(self):
        """'hn' works as alias for 'hackernews'."""
        snap = generate_demo_snapshot(sources=["hn"], limit=3)
        assert all(i.source == SourceType.HACKERNEWS for i in snap.items)

    def test_ph_alias(self):
        """'ph' works as alias for 'producthunt'."""
        snap = generate_demo_snapshot(sources=["ph"], limit=3)
        assert all(i.source == SourceType.PRODUCTHUNT for i in snap.items)

    def test_items_have_valid_urls(self):
        """All demo items have URLs."""
        snap = generate_demo_snapshot(limit=5, seed=42)
        for item in snap.items:
            assert item.url.startswith("http")

    def test_items_have_titles(self):
        """All demo items have non-empty titles."""
        snap = generate_demo_snapshot(limit=5, seed=42)
        for item in snap.items:
            assert len(item.title) > 0

    def test_github_items_have_stars(self):
        """GitHub items have star counts."""
        snap = generate_demo_snapshot(sources=["github"], limit=5, seed=42)
        for item in snap.items:
            assert item.repo_stars is not None
            assert item.repo_stars >= 0

    def test_hn_items_have_extra(self):
        """HN items have comment count in extra."""
        snap = generate_demo_snapshot(sources=["hackernews"], limit=5, seed=42)
        for item in snap.items:
            assert "comment_count" in item.extra
            assert "hn_id" in item.extra

    def test_reddit_items_have_subreddit(self):
        """Reddit items have subreddit tags."""
        snap = generate_demo_snapshot(sources=["reddit"], limit=5, seed=42)
        for item in snap.items:
            assert "subreddit" in item.extra

    def test_arxiv_items_have_categories(self):
        """arXiv items have category tags."""
        snap = generate_demo_snapshot(sources=["arxiv"], limit=5, seed=42)
        for item in snap.items:
            assert len(item.tags) > 0

    def test_to_dict(self):
        """Demo items can be serialized to dict."""
        snap = generate_demo_snapshot(limit=3, seed=42)
        for item in snap.items:
            d = item.to_dict()
            assert "title" in d
            assert "source" in d
            assert "url" in d


class TestDemoGenerators:
    """Test individual generator functions."""

    def test_gen_github(self):
        items = _gen_github(5, datetime.now(timezone.utc))
        assert len(items) == 5
        assert all(i.source == SourceType.GITHUB for i in items)

    def test_gen_hn(self):
        items = _gen_hn(5, datetime.now(timezone.utc))
        assert len(items) == 5
        assert all(i.source == SourceType.HACKERNEWS for i in items)

    def test_gen_reddit(self):
        items = _gen_reddit(5, datetime.now(timezone.utc))
        assert len(items) == 5
        assert all(i.source == SourceType.REDDIT for i in items)

    def test_gen_arxiv(self):
        items = _gen_arxiv(5, datetime.now(timezone.utc))
        assert len(items) == 5
        assert all(i.source == SourceType.ARXIV for i in items)

    def test_gen_rss(self):
        items = _gen_rss(5, datetime.now(timezone.utc))
        assert len(items) == 5
        assert all(i.source == SourceType.RSS for i in items)

    def test_gen_producthunt(self):
        items = _gen_producthunt(5, datetime.now(timezone.utc))
        assert len(items) == 5
        assert all(i.source == SourceType.PRODUCTHUNT for i in items)

    def test_gen_limit_exceeds_available(self):
        """Requesting more items than available returns what we have."""
        items = _gen_github(100, datetime.now(timezone.utc))
        assert len(items) > 0
        assert len(items) <= 15  # max in _GITHUB_REPOS


# ── Doctor Tests ────────────────────────────────────────────────────


class TestDoctorReport:
    """Tests for DoctorReport dataclass."""

    def test_empty_report(self):
        report = DoctorReport()
        assert report.ok_count == 0
        assert report.warn_count == 0
        assert report.error_count == 0
        assert report.healthy is True  # no errors = healthy

    def test_report_counts(self):
        report = DoctorReport(checks=[
            CheckResult("a", "ok", "good"),
            CheckResult("b", "warn", "hmm"),
            CheckResult("c", "error", "bad"),
            CheckResult("d", "ok", "fine"),
        ])
        assert report.ok_count == 2
        assert report.warn_count == 1
        assert report.error_count == 1
        assert report.healthy is False

    def test_warnings_only_healthy(self):
        """Warnings alone don't make it unhealthy."""
        report = DoctorReport(checks=[
            CheckResult("a", "ok", "good"),
            CheckResult("b", "warn", "hmm"),
        ])
        assert report.healthy is True


class TestCheckResult:
    """Tests for CheckResult dataclass."""

    def test_creation(self):
        r = CheckResult("test", "ok", "all good", 42.5)
        assert r.name == "test"
        assert r.status == "ok"
        assert r.message == "all good"
        assert r.duration_ms == 42.5

    def test_default_duration(self):
        r = CheckResult("test", "ok", "fine")
        assert r.duration_ms == 0.0


class TestDoctorChecks:
    """Tests for individual check functions."""

    def test_python_version(self):
        result = _check_python_version()
        assert result.name == "Python version"
        assert result.status == "ok"  # We know we're on 3.10+

    def test_dependency_rich(self):
        result = _check_dependency("rich")
        assert result.status == "ok"
        assert "v" in result.message

    def test_dependency_nonexistent(self):
        result = _check_dependency("nonexistent_package_xyz", required=True)
        assert result.status == "error"

    def test_dependency_optional_missing(self):
        result = _check_dependency("nonexistent_package_xyz", required=False)
        assert result.status == "warn"

    def test_config_check(self):
        result = _check_config()
        assert result.name == "Config file"
        assert result.status in ("ok", "warn")

    def test_database_check(self):
        result = _check_database()
        assert result.name == "Database"
        assert result.status in ("ok", "warn")


class TestRunDoctor:
    """Test the full doctor command."""

    def test_run_doctor_silent(self):
        """run_doctor without console returns report."""
        report = run_doctor()
        assert isinstance(report, DoctorReport)
        assert len(report.checks) > 0
        # Should have checks for Python, deps, sources, config, db
        check_names = [c.name for c in report.checks]
        assert "Python version" in check_names

    def test_run_doctor_has_source_checks(self):
        """Doctor checks source connectivity."""
        report = run_doctor()
        source_checks = [c for c in report.checks if c.name.startswith("Source:")]
        assert len(source_checks) == 5  # GitHub, HN, Reddit, arXiv, PH

    def test_run_doctor_has_dependency_checks(self):
        """Doctor checks dependencies."""
        report = run_doctor()
        dep_checks = [c for c in report.checks if c.name.startswith("Dependency:")]
        assert len(dep_checks) >= 5  # required + optional deps


# ── CLI Integration Tests ───────────────────────────────────────────


class TestDemoCLI:
    """Test demo command via CLI."""

    def test_demo_json_output(self):
        """Demo --json outputs valid JSON."""
        import json
        from click.testing import CliRunner
        from trend_radar.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["demo", "--json", "--no-banner", "--seed", "42"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "items" in data
        assert len(data["items"]) > 0

    def test_demo_help(self):
        """Demo --help works."""
        from click.testing import CliRunner
        from trend_radar.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["demo", "--help"])
        assert result.exit_code == 0
        assert "demo" in result.output.lower()

    def test_demo_limit(self):
        """Demo --limit controls output."""
        import json
        from click.testing import CliRunner
        from trend_radar.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["demo", "--json", "--no-banner", "--limit", "3", "--seed", "42"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        # Each of 6 sources, 3 items each = 18 items
        assert len(data["items"]) <= 18

    def test_demo_sources_filter(self):
        """Demo --sources filters output."""
        import json
        from click.testing import CliRunner
        from trend_radar.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["demo", "--json", "--no-banner", "--sources", "github", "--seed", "42"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        for item in data["items"]:
            assert item["source"] == "github"


class TestDoctorCLI:
    """Test doctor command via CLI."""

    def test_doctor_runs(self):
        """Doctor command runs without error."""
        from click.testing import CliRunner
        from trend_radar.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code == 0

    def test_doctor_output_contains_checks(self):
        """Doctor output shows check results."""
        from click.testing import CliRunner
        from trend_radar.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert "Python version" in result.output

    def test_doctor_help(self):
        """Doctor --help works."""
        from click.testing import CliRunner
        from trend_radar.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["doctor", "--help"])
        assert result.exit_code == 0

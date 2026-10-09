"""Tests for the CSV exporter."""

import csv
import io

from trend_radar.models import IntelItem, SourceType, TrendSnapshot
from trend_radar.exporters.csv_export import CsvRenderer


def _make_snapshot() -> TrendSnapshot:
    return TrendSnapshot(
        items=[
            IntelItem(
                title="test/repo",
                source=SourceType.GITHUB,
                score=1200,
                author="user",
                description="A test repository",
                url="https://github.com/test/repo",
                repo_language="Python",
            ),
            IntelItem(
                title="Show HN: Something",
                source=SourceType.HACKERNEWS,
                score=300,
                url="https://news.ycombinator.com/item?id=123",
            ),
        ],
        sources_queried=["github", "hackernews"],
    )


def test_csv_renderer_produces_csv():
    snap = _make_snapshot()
    renderer = CsvRenderer()
    output = renderer.render(snap)
    assert "rank" in output
    assert "source" in output
    assert "title" in output


def test_csv_has_correct_columns():
    snap = _make_snapshot()
    renderer = CsvRenderer()
    output = renderer.render(snap)
    reader = csv.reader(io.StringIO(output))
    rows = list(reader)
    assert len(rows) >= 3  # header + 2 items
    header = rows[0]
    assert "rank" in header
    assert "source" in header
    assert "title" in header
    assert "score" in header
    assert "url" in header


def test_csv_contains_items():
    snap = _make_snapshot()
    renderer = CsvRenderer()
    output = renderer.render(snap)
    assert "test/repo" in output
    assert "Show HN: Something" in output
    assert "1200" in output


def test_csv_sorted_by_score():
    snap = _make_snapshot()
    renderer = CsvRenderer()
    output = renderer.render(snap)
    reader = csv.reader(io.StringIO(output))
    rows = list(reader)
    # First item should have rank 1
    assert rows[1][0] == "1"
    # Higher score item should be first
    assert "1200" in rows[1][5]


def test_csv_empty_snapshot():
    snap = TrendSnapshot()
    renderer = CsvRenderer()
    output = renderer.render(snap)
    reader = csv.reader(io.StringIO(output))
    rows = list(reader)
    assert len(rows) == 1  # Only header

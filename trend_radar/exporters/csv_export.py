"""CSV exporter — exports trend data as CSV."""

import csv
import io
from typing import Optional

from trend_radar.models import IntelItem, TrendSnapshot


class CsvRenderer:
    """Renders trend data as CSV."""

    def render(self, snapshot: TrendSnapshot) -> str:
        """Export snapshot items as CSV string."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "rank", "source", "title", "url", "description", "score",
            "author", "repo_language", "repo_stars", "tags", "fetched_at"
        ])

        sorted_items = sorted(snapshot.items, key=lambda x: x.score, reverse=True)
        for i, item in enumerate(sorted_items, 1):
            writer.writerow([
                i,
                item.source.value,
                item.title,
                item.url,
                item.description[:200],
                item.score,
                item.author,
                item.repo_language or "",
                item.repo_stars or "",
                ";".join(item.tags),
                item.fetched_at.isoformat(),
            ])

        return output.getvalue()

"""HTML dashboard exporter — generates a standalone interactive HTML file."""

from datetime import datetime
from typing import Optional

from trend_radar.models import IntelItem, SourceType, TrendSnapshot


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
    SourceType.GITHUB: "#6e5494",
    SourceType.HACKERNEWS: "#ff6600",
    SourceType.REDDIT: "#ff4500",
    SourceType.ARXIV: "#b31b1b",
    SourceType.RSS: "#ee802f",
    SourceType.PRODUCTHUNT: "#da552f",
    SourceType.YOUTUBE: "#ff0000",
    SourceType.DEVTO: "#3b49df",
    SourceType.LOBSTERS: "#ac130d",
    SourceType.MEDIUM: "#00ab6c",
    SourceType.NEWS: "#1d70b8",
}


class HtmlRenderer:
    """Renders a TrendSnapshot as a beautiful standalone HTML dashboard."""

    def render(self, snapshot: TrendSnapshot, title: str = "Trend Radar") -> str:
        """Generate a complete HTML document."""
        ts = snapshot.timestamp.strftime("%Y-%m-%d %H:%M UTC")
        keywords = snapshot.keywords(20)

        # Build source sections
        sections_html = ""
        for source in SourceType:
            items = snapshot.by_source(source)
            if not items:
                continue
            emoji = SOURCE_EMOJI.get(source, "•")
            color = SOURCE_COLORS.get(source, "#666")
            items_sorted = sorted(items, key=lambda x: x.score, reverse=True)[:10]
            sections_html += self._render_source_section(source, items_sorted, emoji, color)

        # Build keyword cloud
        kw_html = self._render_keywords(keywords)

        return self._build_page(title, ts, snapshot, sections_html, kw_html, keywords)

    def _render_source_section(
        self, source: SourceType, items: list[IntelItem], emoji: str, color: str
    ) -> str:
        max_score = max((it.score for it in items), default=1) or 1
        rows = ""
        for i, item in enumerate(items, 1):
            bar_pct = int(item.score / max_score * 100) if max_score > 0 else 0
            score_display = f"{item.score / 1000:.1f}k" if item.score >= 1000 else str(item.score)
            desc = (item.description[:120] + "…") if len(item.description) > 120 else item.description
            author_html = f'<span class="author">👤 {item.author}</span>' if item.author else ""
            lang_html = f'<span class="lang">{item.repo_language}</span>' if item.repo_language else ""

            rows += f"""
            <tr>
              <td class="rank">{i}</td>
              <td class="title-cell">
                <a href="{item.url}" target="_blank">{self._escape(item.title)}</a>
                <div class="item-meta">{lang_html} {author_html}</div>
                <div class="item-desc">{self._escape(desc)}</div>
              </td>
              <td class="score-cell">
                <div class="score-value" style="color:{color}">{score_display}</div>
                <div class="score-bar"><div class="score-fill" style="width:{bar_pct}%;background:{color}"></div></div>
              </td>
            </tr>"""

        return f"""
    <div class="source-section">
      <div class="source-header" style="border-left:4px solid {color}">
        <span class="source-emoji">{emoji}</span>
        <span class="source-name">{source.value.upper()}</span>
        <span class="source-count">{len(items)} items</span>
      </div>
      <table class="source-table">
        <thead><tr><th>#</th><th>Title</th><th>Score</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""

    def _render_keywords(self, keywords: list[tuple[str, int]]) -> str:
        if not keywords:
            return ""
        max_count = max(c for _, c in keywords) if keywords else 1
        tags = ""
        for word, count in keywords[:20]:
            size = max(0.8, min(2.0, count / max_count * 2))
            opacity = max(0.5, min(1.0, count / max_count + 0.3))
            tags += f'<span class="keyword" style="font-size:{size}em;opacity:{opacity}">{self._escape(word)}</span> '
        return f"""
    <div class="keywords-section">
      <h2>🔑 Trending Keywords</h2>
      <div class="keyword-cloud">{tags}</div>
    </div>"""

    def _build_page(
        self, title: str, ts: str, snapshot: TrendSnapshot,
        sections_html: str, kw_html: str, keywords: list[tuple[str, int]]
    ) -> str:
        # Source distribution for chart
        source_counts = {}
        for item in snapshot.items:
            s = item.source.value
            source_counts[s] = source_counts.get(s, 0) + 1
        chart_labels = list(source_counts.keys())
        chart_values = list(source_counts.values())
        chart_colors = [SOURCE_COLORS.get(SourceType(s), "#666") for s in chart_labels]

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{self._escape(title)} — {ts}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; line-height: 1.6; }}
.container {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}
.header {{ text-align: center; padding: 40px 20px; border-bottom: 1px solid #21262d; margin-bottom: 30px; }}
.header h1 {{ font-size: 2.2em; color: #58a6ff; margin-bottom: 8px; }}
.header .subtitle {{ color: #8b949e; font-size: 1.1em; }}
.stats-bar {{ display: flex; justify-content: center; gap: 30px; margin-top: 20px; flex-wrap: wrap; }}
.stat {{ text-align: center; }}
.stat .num {{ font-size: 1.8em; font-weight: bold; color: #58a6ff; }}
.stat .label {{ color: #8b949e; font-size: 0.85em; }}
.source-section {{ margin-bottom: 30px; }}
.source-header {{ display: flex; align-items: center; gap: 10px; padding: 12px 16px; background: #161b22; border-radius: 8px 8px 0 0; }}
.source-emoji {{ font-size: 1.3em; }}
.source-name {{ font-weight: bold; font-size: 1.1em; }}
.source-count {{ color: #8b949e; margin-left: auto; font-size: 0.85em; }}
.source-table {{ width: 100%; border-collapse: collapse; background: #0d1117; }}
.source-table th {{ text-align: left; padding: 10px 14px; background: #161b22; color: #8b949e; font-weight: 600; font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.05em; }}
.source-table td {{ padding: 12px 14px; border-bottom: 1px solid #21262d; }}
.source-table tr:hover {{ background: #161b22; }}
.rank {{ color: #8b949e; font-weight: bold; width: 40px; }}
.title-cell a {{ color: #58a6ff; text-decoration: none; font-weight: 600; font-size: 1.05em; }}
.title-cell a:hover {{ text-decoration: underline; }}
.item-meta {{ margin-top: 4px; font-size: 0.8em; }}
.item-desc {{ color: #8b949e; font-size: 0.85em; margin-top: 4px; }}
.author {{ color: #8b949e; margin-right: 10px; }}
.lang {{ background: #21262d; padding: 2px 8px; border-radius: 4px; color: #58a6ff; font-size: 0.8em; margin-right: 8px; }}
.score-cell {{ text-align: right; width: 120px; }}
.score-value {{ font-weight: bold; font-size: 1.1em; }}
.score-bar {{ width: 100%; height: 4px; background: #21262d; border-radius: 2px; margin-top: 6px; }}
.score-fill {{ height: 100%; border-radius: 2px; transition: width 0.3s; }}
.keywords-section {{ margin-top: 30px; padding: 20px; background: #161b22; border-radius: 8px; }}
.keywords-section h2 {{ margin-bottom: 15px; font-size: 1.2em; }}
.keyword-cloud {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
.keyword {{ color: #58a6ff; background: #0d1117; padding: 4px 12px; border-radius: 16px; border: 1px solid #21262d; font-weight: 500; }}
.chart-section {{ margin-top: 30px; padding: 20px; background: #161b22; border-radius: 8px; }}
.chart-section h2 {{ margin-bottom: 15px; font-size: 1.2em; }}
.chart-bars {{ display: flex; flex-direction: column; gap: 8px; }}
.chart-row {{ display: flex; align-items: center; gap: 12px; }}
.chart-label {{ width: 120px; font-weight: 600; text-align: right; }}
.chart-bar-bg {{ flex: 1; height: 24px; background: #0d1117; border-radius: 4px; overflow: hidden; }}
.chart-bar-fill {{ height: 100%; border-radius: 4px; display: flex; align-items: center; padding-left: 8px; font-size: 0.8em; font-weight: bold; color: white; min-width: 30px; }}
.footer {{ text-align: center; padding: 30px; color: #8b949e; font-size: 0.85em; border-top: 1px solid #21262d; margin-top: 40px; }}
@media (max-width: 768px) {{
  .container {{ padding: 10px; }}
  .stats-bar {{ gap: 15px; }}
  .chart-label {{ width: 80px; font-size: 0.85em; }}
}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>📡 {self._escape(title)}</h1>
    <div class="subtitle">{ts}</div>
    <div class="stats-bar">
      <div class="stat"><div class="num">{snapshot.item_count}</div><div class="label">Items</div></div>
      <div class="stat"><div class="num">{len(snapshot.sources_queried)}</div><div class="label">Sources</div></div>
      <div class="stat"><div class="num">{len(keywords)}</div><div class="label">Keywords</div></div>
      {'<div class="stat"><div class="num" style="color:#f85149">' + str(len(snapshot.errors)) + '</div><div class="label">Errors</div></div>' if snapshot.errors else ''}
    </div>
  </div>

  {sections_html}

  <div class="chart-section">
    <h2>📊 Source Distribution</h2>
    <div class="chart-bars">
      {"".join(f'<div class="chart-row"><span class="chart-label">{SOURCE_EMOJI.get(SourceType(l), "•")} {l}</span><div class="chart-bar-bg"><div class="chart-bar-fill" style="width:{int(v/max(chart_values)*100)}%;background:{c}">{v}</div></div></div>' for l, v, c in zip(chart_labels, chart_values, chart_colors))}
    </div>
  </div>

  {kw_html}

  <div class="footer">
    Generated by <strong>Trend Radar</strong> · {ts}
  </div>
</div>
</body>
</html>"""

    @staticmethod
    def _escape(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

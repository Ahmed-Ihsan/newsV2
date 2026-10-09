"""Hermes Agent tool integration for Trend Radar.

Install this as a Hermes tool to use trend-radar from within Hermes conversations.

Usage in Hermes config.yaml:
    tools:
      trend_radar:
        enabled: true
"""

import json
import os
from typing import Optional

from trend_radar.core import TrendRadar


def get_radar() -> TrendRadar:
    """Get a configured TrendRadar instance."""
    db_path = os.environ.get("TREND_RADAR_DB", os.path.expanduser("~/.trend-radar/trends.db"))
    github_token = os.environ.get("GITHUB_TOKEN", "")
    return TrendRadar(db_path=db_path, github_token=github_token)


def trend_fetch(sources: str = "github,hackernews,reddit", limit: int = 15) -> str:
    """Fetch trending intel from multiple sources.

    Args:
        sources: Comma-separated source names (github,hackernews,reddit,arxiv,rss,producthunt)
        limit: Number of items per source
    """
    radar = get_radar()
    source_list = sources.split(",")
    snapshot = radar.collect(sources=source_list, limit=limit, save=True)

    result = {
        "status": "ok",
        "sources": snapshot.sources_queried,
        "item_count": snapshot.item_count,
        "top_items": [
            {"title": i.title, "source": i.source.value, "score": i.score, "url": i.url}
            for i in snapshot.top(10)
        ],
        "keywords": snapshot.keywords(15),
        "errors": snapshot.errors,
    }
    return json.dumps(result, ensure_ascii=False)


def trend_search(query: str, sources: str = "github,arxiv", limit: int = 20) -> str:
    """Search across tech sources for a query.

    Args:
        query: Search query
        sources: Comma-separated source names
        limit: Max results
    """
    radar = get_radar()
    items = radar.search(query, sources=sources.split(","), limit=limit)

    result = {
        "status": "ok",
        "query": query,
        "count": len(items),
        "items": [
            {"title": i.title, "source": i.source.value, "score": i.score, "url": i.url, "desc": i.description[:100]}
            for i in items
        ],
    }
    return json.dumps(result, ensure_ascii=False)


def trend_keywords(days: int = 7) -> str:
    """Get trending keywords from recent data.

    Args:
        days: Number of days to look back
    """
    radar = get_radar()
    kw = radar.store.get_keyword_trends(days=days)

    result = {
        "status": "ok",
        "days": days,
        "keywords": [{"word": w, "count": c} for w, c in kw[:20]],
    }
    return json.dumps(result, ensure_ascii=False)


def trend_analyze() -> str:
    """Analyze recent trends and return opportunity insights."""
    radar = get_radar()
    snapshot = radar.collect_ai_focused(limit=15, save=True)
    analysis = radar.analyze_opportunities(snapshot)

    return json.dumps(analysis, ensure_ascii=False, indent=2)


# Hermes tool schema definitions
TOOLS = [
    {
        "name": "trend_fetch",
        "description": "Fetch trending tech intel from GitHub, Hacker News, Reddit, arXiv, and RSS feeds. Use this to discover what's hot in tech/AI right now.",
        "parameters": {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "string",
                    "description": "Comma-separated source names: github, hackernews, reddit, arxiv, rss",
                    "default": "github,hackernews,reddit",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of items per source",
                    "default": 15,
                },
            },
        },
        "handler": trend_fetch,
    },
    {
        "name": "trend_search",
        "description": "Search across all tech sources for a specific topic. Use to find repos, papers, discussions about a topic.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "sources": {
                    "type": "string",
                    "description": "Comma-separated sources to search",
                    "default": "github,arxiv",
                },
                "limit": {"type": "integer", "description": "Max results", "default": 20},
            },
            "required": ["query"],
        },
        "handler": trend_search,
    },
    {
        "name": "trend_keywords",
        "description": "Get trending keywords from recent tech intelligence data. Shows what topics are heating up.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Days to look back", "default": 7},
            },
        },
        "handler": trend_keywords,
    },
    {
        "name": "trend_analyze",
        "description": "Analyze recent trends across all sources and return AI/tech opportunity insights. Use when deciding what to build next.",
        "parameters": {"type": "object", "properties": {}},
        "handler": trend_analyze,
    },
]

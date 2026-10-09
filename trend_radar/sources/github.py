"""GitHub data source — API search + Trending page scraping."""

import os
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from trend_radar.models import IntelItem, SourceType
from trend_radar.sources import DataSource


class GitHubSource(DataSource):
    """Fetches trending repos and search results from GitHub."""

    name = "github"
    source_type = SourceType.GITHUB
    requires_auth = False

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def fetch(self, limit: int = 25, **kwargs) -> list[IntelItem]:
        """Fetch trending repos — tries API first, falls back to scraping."""
        items = self._fetch_trending_api(limit, **kwargs)
        if not items:
            items = self._fetch_trending_scrape(limit, **kwargs)
        return items[:limit]

    def _fetch_trending_api(
        self, limit: int, language: str = "", since: str = "daily", **kwargs
    ) -> list[IntelItem]:
        """Use GitHub Search API to approximate trending."""
        # Map time ranges
        from datetime import datetime, timedelta

        days = {"daily": 1, "weekly": 7, "monthly": 30}.get(since, 1)
        date_from = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

        query = f"created:>{date_from} stars:>10"
        if language:
            query += f" language:{language}"

        url = "https://api.github.com/search/repositories"
        params = {"q": query, "sort": "stars", "order": "desc", "per_page": min(limit, 100)}

        try:
            with httpx.Client(timeout=15, headers=self.headers) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return []

        items = []
        for repo in data.get("items", [])[:limit]:
            items.append(
                IntelItem(
                    title=repo["full_name"],
                    source=SourceType.GITHUB,
                    url=repo["html_url"],
                    description=repo.get("description", "") or "",
                    score=repo.get("stargazers_count", 0),
                    author=repo.get("owner", {}).get("login", ""),
                    repo_stars=repo.get("stargazers_count", 0),
                    repo_language=repo.get("language"),
                    repo_forks=repo.get("forks_count", 0),
                    tags=[repo["language"]] if repo.get("language") else [],
                )
            )
        return items

    def _fetch_trending_scrape(
        self, limit: int, language: str = "", since: str = "daily", **kwargs
    ) -> list[IntelItem]:
        """Scrape GitHub Trending page as fallback."""
        url = f"https://github.com/trending/{language}"
        if since != "daily":
            url += f"?since={since}"

        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(url, follow_redirects=True)
                resp.raise_for_status()
        except Exception:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        items = []

        for article in soup.select("article.Box-row")[:limit]:
            # Repo name
            h2 = article.select_one("h2 a")
            if not h2:
                continue
            name = h2.get("href", "").strip("/")

            # Description
            p = article.select_one("p")
            desc = p.get_text(strip=True) if p else ""

            # Stars
            star_span = article.select_one("a[href*='/stargazers']")
            stars_text = star_span.get_text(strip=True).replace(",", "") if star_span else "0"
            try:
                stars = int(stars_text)
            except ValueError:
                stars = 0

            # Language
            lang_span = article.select_one("span[itemprop='programmingLanguage']")
            lang = lang_span.get_text(strip=True) if lang_span else ""

            items.append(
                IntelItem(
                    title=name,
                    source=SourceType.GITHUB,
                    url=f"https://github.com/{name}",
                    description=desc,
                    score=stars,
                    author=name.split("/")[0] if "/" in name else "",
                    repo_stars=stars,
                    repo_language=lang if lang else None,
                    tags=[lang] if lang else [],
                )
            )

        return items

    def search(
        self, query: str, limit: int = 25, language: str = "", min_stars: int = 0
    ) -> list[IntelItem]:
        """Search GitHub repositories."""
        q = query
        if language:
            q += f" language:{language}"
        if min_stars:
            q += f" stars:>={min_stars}"

        url = "https://api.github.com/search/repositories"
        params = {"q": q, "sort": "stars", "order": "desc", "per_page": min(limit, 100)}

        try:
            with httpx.Client(timeout=15, headers=self.headers) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return []

        items = []
        for repo in data.get("items", [])[:limit]:
            items.append(
                IntelItem(
                    title=repo["full_name"],
                    source=SourceType.GITHUB,
                    url=repo["html_url"],
                    description=repo.get("description", "") or "",
                    score=repo.get("stargazers_count", 0),
                    author=repo.get("owner", {}).get("login", ""),
                    repo_stars=repo.get("stargazers_count", 0),
                    repo_language=repo.get("language"),
                    repo_forks=repo.get("forks_count", 0),
                )
            )
        return items

"""GitHub data source — Trending page scraping + API search fallback."""

import logging
import os
import re
from typing import Optional

import httpx
from httpx import HTTPStatusError
from bs4 import BeautifulSoup

from trend_radar.models import IntelItem, SourceType
from trend_radar.sources import DataSource

logger = logging.getLogger(__name__)

# The trending page serves a JS-heavy app to non-browser clients
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_STARS_TODAY_RE = re.compile(
    r"([\d,]+)\s+stars?\s+(?:today|this week|this month)", re.IGNORECASE
)


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
        """Fetch trending repos — scrape the trending page first, Search API fallback."""
        errors: list[str] = []

        try:
            items = self._fetch_trending_scrape(limit, **kwargs)
        except Exception as e:
            logger.warning("github: trending page scrape failed: %s", e)
            errors.append(f"trending page: {e}")
            items = []

        if not items:
            try:
                items = self._fetch_trending_api(limit, **kwargs)
            except Exception as e:
                logger.warning("github: Search API fallback failed: %s", e)
                errors.append(f"search api: {e}")

        if not items:
            raise RuntimeError(
                f"github: no trending repos obtainable "
                f"({'; '.join(errors) or 'empty results'})"
            )
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
        except HTTPStatusError as e:
            raise RuntimeError(
                f"github Search API: HTTP {e.response.status_code} from {url}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"github Search API: request to {url} failed: {e}") from e

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
        """Scrape GitHub Trending page.

        Raises on request failure; returns [] when the page parses to no
        articles so the caller can fall back to the Search API.
        """
        url = f"https://github.com/trending/{language}".rstrip("/")
        if since != "daily":
            url += f"?since={since}"

        try:
            with httpx.Client(timeout=15, headers=BROWSER_HEADERS) as client:
                resp = client.get(url, follow_redirects=True)
                resp.raise_for_status()
        except HTTPStatusError as e:
            raise RuntimeError(
                f"github trending page: HTTP {e.response.status_code} from {url}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"github trending page: request to {url} failed: {e}") from e

        soup = BeautifulSoup(resp.text, "html.parser")
        items = []

        for article in soup.select("article.Box-row")[:limit]:
            # Repo full name lives in the h2 link's href
            h2 = article.select_one("h2 a")
            if not h2:
                continue
            name = (h2.get("href") or "").strip("/")
            if not name:
                continue

            # Description
            p = article.select_one("p")
            desc = p.get_text(strip=True) if p else ""

            # Total stars
            star_span = article.select_one("a[href$='/stargazers']")
            stars_text = star_span.get_text(strip=True).replace(",", "") if star_span else "0"
            try:
                stars = int(stars_text)
            except ValueError:
                stars = 0

            # Language
            lang_span = article.select_one("span[itemprop='programmingLanguage']")
            lang = lang_span.get_text(strip=True) if lang_span else ""

            # "1,234 stars today" badge (weekly/monthly pages say this week/month)
            stars_today = None
            m = _STARS_TODAY_RE.search(article.get_text(" ", strip=True))
            if m:
                try:
                    stars_today = int(m.group(1).replace(",", ""))
                except ValueError:
                    stars_today = None

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
                    extra={"stars_today": stars_today},
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

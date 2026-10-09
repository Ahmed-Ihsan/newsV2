"""Product Hunt data source — scraping trending products."""

import httpx
from bs4 import BeautifulSoup

from trend_radar.models import IntelItem, SourceType
from trend_radar.sources import DataSource


class ProductHuntSource(DataSource):
    """Fetches trending products from Product Hunt."""

    name = "producthunt"
    source_type = SourceType.PRODUCTHUNT

    BASE_URL = "https://www.producthunt.com"

    def fetch(self, limit: int = 25, **kwargs) -> list[IntelItem]:
        """Fetch today's top products from Product Hunt."""
        # Use the /topics/tech or front page
        return self._fetch_frontend(limit)

    def _fetch_frontend(self, limit: int) -> list[IntelItem]:
        """Scrape Product Hunt homepage for trending products."""
        headers = {
            "User-Agent": "TrendRadar/0.1 (tech intelligence aggregator)",
            "Accept": "text/html,application/xhtml+xml",
        }

        try:
            with httpx.Client(timeout=20, headers=headers, follow_redirects=True) as client:
                resp = client.get(f"{self.BASE_URL}/")
                resp.raise_for_status()
        except Exception:
            return []

        return self._parse_html(resp.text, limit)

    def _parse_html(self, html: str, limit: int) -> list[IntelItem]:
        """Parse Product Hunt HTML for product data."""
        soup = BeautifulSoup(html, "html.parser")
        items = []

        # Product Hunt uses data attributes and specific class patterns
        # Look for product cards/links
        product_links = soup.select('a[href^="/posts/"]')

        seen = set()
        for link in product_links:
            href = link.get("href", "")
            if href in seen:
                continue
            seen.add(href)

            title = link.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            # Try to find vote count nearby
            parent = link.find_parent(["div", "li", "article"])
            votes = 0
            if parent:
                # Look for vote count patterns
                vote_el = parent.find(string=lambda t: t and t.strip().isdigit())
                if vote_el:
                    try:
                        votes = int(vote_el.strip())
                    except ValueError:
                        pass

                # Look for description
                desc_el = parent.find("p")
                desc = desc_el.get_text(strip=True)[:200] if desc_el else ""
            else:
                desc = ""

            url = f"{self.BASE_URL}{href}" if href.startswith("/") else href

            items.append(
                IntelItem(
                    title=title,
                    source=SourceType.PRODUCTHUNT,
                    url=url,
                    description=desc,
                    score=votes,
                    tags=["producthunt"],
                    extra={"source": "producthunt"},
                )
            )

            if len(items) >= limit:
                break

        return items

    def search(self, query: str, limit: int = 25, **kwargs) -> list[IntelItem]:
        """Search Product Hunt for products."""
        headers = {
            "User-Agent": "TrendRadar/0.1 (tech intelligence aggregator)",
        }
        params = {"q": query}

        try:
            with httpx.Client(timeout=20, headers=headers, follow_redirects=True) as client:
                resp = client.get(f"{self.BASE_URL}/search", params=params)
                resp.raise_for_status()
        except Exception:
            return []

        return self._parse_html(resp.text, limit)

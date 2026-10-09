"""Product Hunt data source — Atom feed with HTML scraping fallback."""

import logging
import re
import xml.etree.ElementTree as ET

import httpx
from httpx import HTTPStatusError
from bs4 import BeautifulSoup

from trend_radar.models import IntelItem, SourceType
from trend_radar.sources import DataSource

logger = logging.getLogger(__name__)

_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _strip_html(text: str) -> str:
    """Strip HTML tags from a snippet."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


class ProductHuntSource(DataSource):
    """Fetches trending products from Product Hunt."""

    name = "producthunt"
    source_type = SourceType.PRODUCTHUNT

    BASE_URL = "https://www.producthunt.com"
    FEED_URL = "https://www.producthunt.com/feed"

    def fetch(self, limit: int = 25, **kwargs) -> list[IntelItem]:
        """Fetch today's top products from Product Hunt."""
        return self._fetch_feed(limit)

    def _fetch_feed(self, limit: int) -> list[IntelItem]:
        """Fetch and parse the Product Hunt Atom feed."""
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/atom+xml, application/xml, text/xml",
        }

        try:
            with httpx.Client(timeout=20, headers=headers, follow_redirects=True) as client:
                resp = client.get(self.FEED_URL)
                resp.raise_for_status()
        except HTTPStatusError as e:
            raise RuntimeError(
                f"producthunt: HTTP {e.response.status_code} from {self.FEED_URL}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"producthunt: request to {self.FEED_URL} failed: {e}") from e

        items = self._parse_atom(resp.text, limit)
        if not items:
            raise RuntimeError(f"producthunt: no products found in {self.FEED_URL} response")
        return items

    def _parse_atom(self, xml_text: str, limit: int) -> list[IntelItem]:
        """Parse the Product Hunt Atom feed into items."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.warning("producthunt: feed unparsable: %s", e)
            return []

        items = []
        for entry in root.findall("atom:entry", _ATOM_NS)[:limit]:
            title = (entry.findtext("atom:title", namespaces=_ATOM_NS) or "").strip()
            if not title:
                continue

            link = ""
            alt_link = ""
            for link_el in entry.findall("atom:link", _ATOM_NS):
                href = link_el.get("href", "")
                if not href:
                    continue
                if link_el.get("rel", "alternate") == "alternate":
                    alt_link = href
                    break
                if not link:
                    link = href
            link = alt_link or link

            body = _strip_html(
                entry.findtext("atom:content", namespaces=_ATOM_NS)
                or entry.findtext("atom:summary", namespaces=_ATOM_NS)
                or ""
            )[:200]
            author = (
                entry.findtext("atom:author/atom:name", namespaces=_ATOM_NS) or ""
            ).strip()
            published = (
                entry.findtext("atom:published", namespaces=_ATOM_NS)
                or entry.findtext("atom:updated", namespaces=_ATOM_NS)
                or ""
            ).strip()

            items.append(
                IntelItem(
                    title=title,
                    source=SourceType.PRODUCTHUNT,
                    url=link,
                    description=body,
                    score=0,  # the feed carries no vote counts
                    author=author,
                    tags=["producthunt"],
                    extra={"source": "producthunt", "published": published},
                )
            )

        return items

    def _fetch_frontend(self, limit: int) -> list[IntelItem]:
        """Scrape Product Hunt homepage for trending products (legacy path)."""
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

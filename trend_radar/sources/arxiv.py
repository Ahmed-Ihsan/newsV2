"""arXiv data source — API + RSS feed."""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from trend_radar.models import IntelItem, SourceType
from trend_radar.sources import DataSource


class ArxivSource(DataSource):
    """Fetches papers from arXiv."""

    name = "arxiv"
    source_type = SourceType.ARXIV

    CATEGORIES = {
        "ai": "cs.AI",
        "ml": "cs.LG",
        "nlp": "cs.CL",
        "cv": "cs.CV",
        "ir": "cs.IR",
        "all": "cs.AI+OR+cs.LG+OR+cs.CL",
    }

    def fetch(
        self,
        limit: int = 25,
        category: str = "ai",
        sort_by: str = "submittedDate",
        **kwargs,
    ) -> list[IntelItem]:
        """Fetch recent papers from arXiv API."""
        cat = self.CATEGORIES.get(category, category)
        query = f"cat:{cat}"

        url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": query,
            "start": 0,
            "max_results": limit,
            "sortBy": sort_by,
            "sortOrder": "descending",
        }

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
        except Exception:
            return []

        return self._parse_feed(resp.text, limit)

    def _parse_feed(self, xml_text: str, limit: int) -> list[IntelItem]:
        """Parse arXiv Atom feed."""
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        items = []
        for entry in root.findall("atom:entry", ns)[:limit]:
            title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
            summary = entry.findtext("atom:summary", "", ns).strip().replace("\n", " ")[:300]

            # Get link
            link = ""
            for l in entry.findall("atom:link", ns):
                if l.get("type") == "text/html":
                    link = l.get("href", "")
                    break
            if not link:
                id_el = entry.findtext("atom:id", "", ns)
                link = id_el.replace("http://arxiv.org/abs/", "https://arxiv.org/abs/")

            # Get authors
            authors = [a.findtext("atom:name", "", ns) for a in entry.findall("atom:author", ns)]
            author_str = authors[0] if authors else ""
            if len(authors) > 1:
                author_str += f" +{len(authors)-1}"

            # Get categories/tags
            tags = []
            for cat in entry.findall("arxiv:primary_category", ns):
                tags.append(cat.get("term", ""))
            for cat in entry.findall("atom:category", ns):
                t = cat.get("term", "")
                if t and t not in tags:
                    tags.append(t)

            # Published date
            published = entry.findtext("atom:published", "", ns)

            items.append(
                IntelItem(
                    title=title,
                    source=SourceType.ARXIV,
                    url=link,
                    description=summary,
                    score=0,  # arXiv papers don't have scores
                    author=author_str,
                    tags=tags[:5],
                    extra={
                        "published": published,
                        "all_authors": authors,
                        "arxiv_id": link.split("/abs/")[-1] if "/abs/" in link else "",
                    },
                )
            )

        return items

    def search(self, query: str, limit: int = 25, **kwargs) -> list[IntelItem]:
        """Search arXiv papers."""
        url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
        }

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
        except Exception:
            return []

        return self._parse_feed(resp.text, limit)

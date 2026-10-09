"""Shared RSS/Atom helpers for feed-based sources (YouTube, Medium, News)."""

import concurrent.futures
import xml.etree.ElementTree as ET

import httpx

from trend_radar.models import IntelItem, SourceType

ATOM = "{http://www.w3.org/2005/Atom}"
MEDIA = "{http://search.yahoo.com/mrss/}"
USER_AGENT = "Mozilla/5.0 (compatible; TrendRadar/1.0)"


def fetch_text(url: str, timeout: int = 15) -> str:
    """GET a URL and return the body, or "" on any failure."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text
    except Exception:
        return ""


def parse_feed(text: str, source: SourceType, label: str, limit: int) -> list[IntelItem]:
    """Parse an RSS 2.0 or Atom document into IntelItems tagged with `label`."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []

    items: list[IntelItem] = []

    for el in root.iter("item"):
        title = (el.findtext("title") or "").strip()
        if not title:
            continue
        items.append(IntelItem(
            title=title,
            source=source,
            url=(el.findtext("link") or "").strip(),
            description=(el.findtext("description") or "").strip()[:300],
            author=(el.findtext("{http://purl.org/dc/elements/1.1/}creator") or "").strip(),
            tags=[label],
            extra={"feed": label},
        ))

    for el in root.findall(f"{ATOM}entry"):
        title = (el.findtext(f"{ATOM}title") or "").strip()
        if not title:
            continue
        link_el = el.find(f"{ATOM}link")
        group = el.find(f"{MEDIA}group")
        stats = group.find(f"{MEDIA}community/{MEDIA}statistics") if group is not None else None
        views = int(stats.get("views", 0)) if stats is not None else 0
        desc = (group.findtext(f"{MEDIA}description") if group is not None else None) \
            or el.findtext(f"{ATOM}summary") or ""
        items.append(IntelItem(
            title=title,
            source=source,
            url=link_el.get("href", "") if link_el is not None else "",
            description=desc.strip()[:300],
            score=views,
            author=(el.findtext(f"{ATOM}author/{ATOM}name") or "").strip(),
            tags=[label],
            extra={"feed": label},
        ))

    return items[:limit]


def fetch_feeds(feeds: dict[str, str], source: SourceType, limit: int, per_feed: int | None = None) -> list[IntelItem]:
    """Fetch several feeds in parallel and return up to `limit` items, round-robin across feeds."""
    if not feeds:
        return []
    per_feed = per_feed or limit

    def _one(label: str, url: str) -> list[IntelItem]:
        return parse_feed(fetch_text(url), source, label, per_feed)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_one, label, url) for label, url in feeds.items()]
        batches = [f.result() for f in futures]

    # Interleave so one busy feed doesn't crowd out the others.
    items: list[IntelItem] = []
    for rank in range(max((len(b) for b in batches), default=0)):
        for batch in batches:
            if rank < len(batch):
                items.append(batch[rank])
    return items[:limit]

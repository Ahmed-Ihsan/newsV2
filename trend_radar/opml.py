"""OPML import for RSS feeds — easy feed setup for power users.

Supports importing RSS feed lists from:
- OPML files (standard RSS reader export format)
- Plain text URLs (one per line)
- JSON feed lists
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


def import_opml(opml_path: str) -> dict[str, str]:
    """Import RSS feeds from an OPML file.

    OPML is the standard format for exporting RSS feed lists from
    feed readers like Feedly, Inoreader, NewsBlur, etc.

    Args:
        opml_path: Path to .opml or .xml file.

    Returns:
        Dict mapping feed title to feed URL.

    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If file is not valid OPML.
    """
    path = Path(opml_path)
    if not path.exists():
        raise FileNotFoundError(f"OPML file not found: {opml_path}")

    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML: {e}") from e

    if root.tag.lower() != "opml":
        raise ValueError(f"Not an OPML file (root element is '{root.tag}')")

    feeds: dict[str, str] = {}
    _extract_feeds(root, feeds)

    if not feeds:
        raise ValueError("No feeds found in OPML file")

    return feeds


def _extract_feeds(element: ET.Element, feeds: dict[str, str]) -> None:
    """Recursively extract feed URLs from OPML outline elements."""
    for outline in element.iter("outline"):
        xml_url = outline.get("xmlUrl") or outline.get("xmlurl")
        if xml_url:
            title = outline.get("title") or outline.get("text") or xml_url
            feeds[title.strip()] = xml_url.strip()


def import_urls(url_list_path: str) -> dict[str, str]:
    """Import RSS feeds from a plain text file (one URL per line).

    Args:
        url_list_path: Path to text file with URLs.

    Returns:
        Dict mapping URL to URL (since no titles available).
    """
    path = Path(url_list_path)
    if not path.exists():
        raise FileNotFoundError(f"URL list file not found: {url_list_path}")

    feeds: dict[str, str] = {}
    for i, line in enumerate(path.read_text().splitlines(), 1):
        url = line.strip()
        if url and url.startswith(("http://", "https://")):
            # Use domain as title
            from urllib.parse import urlparse
            parsed = urlparse(url)
            title = parsed.netloc.replace("www.", "")
            feeds[f"{title} ({i})"] = url

    return feeds


def import_json(json_path: str) -> dict[str, str]:
    """Import RSS feeds from a JSON file.

    Expected format:
        {"feeds": {"name": "url", ...}}
    or
        [{"name": "...", "url": "..."}, ...]

    Args:
        json_path: Path to JSON file.

    Returns:
        Dict mapping feed name to feed URL.
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    data = json.loads(path.read_text())

    if isinstance(data, dict) and "feeds" in data:
        return dict(data["feeds"])
    elif isinstance(data, list):
        feeds = {}
        for item in data:
            if isinstance(item, dict) and "url" in item:
                name = item.get("name", item["url"])
                feeds[name] = item["url"]
        return feeds
    else:
        raise ValueError('JSON must be {"feeds": {...}} or [{"name": ..., "url": ...}]')


def import_feeds(source_path: str) -> dict[str, str]:
    """Auto-detect format and import feeds.

    Supports: .opml, .xml, .json, .txt (URL list)

    Args:
        source_path: Path to feed file.

    Returns:
        Dict mapping feed name to feed URL.
    """
    path = Path(source_path)
    suffix = path.suffix.lower()

    if suffix in (".opml", ".xml"):
        return import_opml(source_path)
    elif suffix == ".json":
        return import_json(source_path)
    elif suffix == ".txt":
        return import_urls(source_path)
    else:
        # Try OPML first, then JSON, then URLs
        try:
            return import_opml(source_path)
        except (ValueError, ET.ParseError):
            pass
        try:
            return import_json(source_path)
        except (json.JSONDecodeError, ValueError):
            pass
        return import_urls(source_path)

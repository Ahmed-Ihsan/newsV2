"""Optional auto-translation of item titles/descriptions (default target: Arabic).

Uses Google Translate's public web endpoint (no API key). Translations are cached
on disk so each string is only translated once. Failures fall back to the original text.
"""

import concurrent.futures
import json
import re
import threading
import time
from pathlib import Path
from typing import Optional

import httpx

from .config import get_config_dir
from .models import IntelItem

ENDPOINT = "https://translate.googleapis.com/translate_a/single"
MYMEMORY = "https://api.mymemory.translated.net/get"
_ARABIC = re.compile(r"[؀-ۿ]")

LANGUAGES = {"ar": "Arabic", "en": "English", "fr": "French", "es": "Spanish", "de": "German", "tr": "Turkish"}


def _mostly_target_script(text: str, target: str) -> bool:
    """True if `text` is already written in the target language's script (Arabic only)."""
    if target != "ar":
        return False
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum(1 for c in letters if _ARABIC.match(c)) / len(letters) > 0.5


class Translator:
    """Translate text into `target` with an on-disk cache."""

    CHUNK_CHARS = 1200   # max raw characters per request (strings are joined by newlines)
    RETRIES = 2
    BLOCK_SECONDS = 120  # after Google rate-limits us, skip it for this long
    FALLBACK_MAX_LEN = 200  # MyMemory has a small daily quota: only translate short strings (titles)

    _blocked_until = 0.0  # shared across instances

    def __init__(self, target: str = "ar", cache_path: Optional[Path] = None, timeout: int = 10):
        self.target = target
        self.timeout = timeout
        self._path = cache_path or (get_config_dir() / f"translations_{target}.json")
        self._lock = threading.Lock()
        self._cache: dict[str, str] = {}
        self._dirty = False
        try:
            self._cache = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass

    # -- backends -----------------------------------------------------------------

    def _google(self, client: httpx.Client, text: str) -> Optional[str]:
        """Google's public endpoint; retries because it rate-limits unpredictably."""
        if time.time() < Translator._blocked_until:
            return None
        params = {"client": "gtx", "sl": "auto", "tl": self.target, "dt": "t", "q": text}
        for attempt in range(self.RETRIES):
            try:
                resp = client.get(ENDPOINT, params=params)
                if resp.status_code == 200:
                    return "".join(seg[0] for seg in resp.json()[0] if seg and seg[0])
                if resp.status_code == 429:
                    break
            except Exception:
                pass
            time.sleep(0.5 * (attempt + 1))
        Translator._blocked_until = time.time() + self.BLOCK_SECONDS
        return None

    def _mymemory(self, client: httpx.Client, text: str) -> Optional[str]:
        """Fallback: MyMemory free API (single short string)."""
        try:
            resp = client.get(MYMEMORY, params={"q": text[:480], "langpair": f"en|{self.target}"})
            if resp.status_code == 200:
                out = resp.json().get("responseData", {}).get("translatedText")
                if out and "MYMEMORY WARNING" not in out:
                    return out
        except Exception:
            pass
        return None

    # -- public API ---------------------------------------------------------------

    def translate_many(self, texts: list[str], client: httpx.Client) -> dict[str, str]:
        """Translate unique strings, batching several per request. Returns {original: translated}."""
        result: dict[str, str] = {}
        pending: list[str] = []
        for t in dict.fromkeys(x.strip() for x in texts if x and x.strip()):
            if _mostly_target_script(t, self.target):
                result[t] = t
            elif t in self._cache:
                result[t] = self._cache[t]
            else:
                pending.append(t.replace("\n", " "))

        # Build chunks of whole strings
        chunks: list[list[str]] = []
        cur: list[str] = []
        size = 0
        for t in pending:
            if cur and size + len(t) > self.CHUNK_CHARS:
                chunks.append(cur)
                cur, size = [], 0
            cur.append(t)
            size += len(t) + 1
        if cur:
            chunks.append(cur)

        def run(chunk: list[str]) -> None:
            out = self._google(client, "\n".join(chunk))
            lines = out.split("\n") if out else []
            if len(lines) == len(chunk):
                pairs = list(zip(chunk, lines))
            else:  # batch got misaligned or failed: do them one by one
                pairs = []
                for t in chunk:
                    single = self._google(client, t)
                    if single is None and len(t) <= self.FALLBACK_MAX_LEN:
                        single = self._mymemory(client, t)
                    pairs.append((t, single or ""))
            with self._lock:
                for orig, tr in pairs:
                    tr = tr.strip()
                    if tr:
                        self._cache[orig] = tr
                        self._dirty = True
                        result[orig] = tr

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(run, chunks))
        return result

    def translate(self, text: str) -> str:
        with httpx.Client(timeout=self.timeout) as client:
            out = self.translate_many([text], client)
        self.save()
        return out.get((text or "").strip(), text)

    def translate_items(self, items: list[IntelItem]) -> list[IntelItem]:
        """Translate title and description in place; originals are kept in item.extra."""
        todo = [i for i in items if not i.extra.get("translated_to")]
        if not todo:
            return items

        texts = [i.title for i in todo] + [i.description for i in todo]
        with httpx.Client(timeout=self.timeout, headers={"User-Agent": "Mozilla/5.0"}) as client:
            tr = self.translate_many(texts, client)

        for item in todo:
            item.extra["original_title"] = item.title
            item.extra["original_description"] = item.description
            item.extra["translated_to"] = self.target
            item.title = tr.get(item.title.strip(), item.title)
            if item.description:
                item.description = tr.get(item.description.strip(), item.description)
        self.save()
        return items

    def save(self) -> None:
        with self._lock:
            if not self._dirty:
                return
            try:
                self._path.write_text(json.dumps(self._cache, ensure_ascii=False), encoding="utf-8")
                self._dirty = False
            except OSError:
                pass

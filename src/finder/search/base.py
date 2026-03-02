"""
src/finder/search/base.py

Purpose
-------
Defines the *contract* for any web-search implementation used by your pipeline,
plus common utilities (LinkedIn profile URL filtering + basic retry/backoff).

This file DOES NOT call any specific provider (e.g., googlesearch). Concrete
clients (e.g., GoogleSearchClient) should live in `web_search.py` and implement
SearchClient.search().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse
import time


# -----------------------------
# Data models
# -----------------------------

@dataclass(frozen=True)
class SearchQuery:
    """
    Normalized search parameters based on your usage of googlesearch.search():
        search(query, num_results=10, unique=True, lang="it", region="eu",
               safe=None, advanced=True)
    """
    query: str
    num_results: int = 10
    unique: bool = True
    lang: str = "it"
    region: str = "eu"
    safe: Optional[str] = None
    advanced: bool = True


@dataclass(frozen=True)
class UrlHit:
    """
    A normalized representation of a found URL.

    Even if you mostly store only URLs, keeping optional fields lets you
    preserve extra data when the provider returns it (e.g., advanced=True).
    """
    url: str
    rank: int
    title: Optional[str] = None
    snippet: Optional[str] = None
    source_query: Optional[str] = None
    raw: Optional[object] = field(default=None, compare=False)


# -----------------------------
# Exceptions
# -----------------------------

class SearchError(RuntimeError):
    """Base exception for search client failures."""


class SearchRetriesExceeded(SearchError):
    """Raised when retry attempts are exhausted."""


# -----------------------------
# LinkedIn profile URL utilities
# -----------------------------

_LINKEDIN_ALLOWED_PATH_PREFIXES: Tuple[str, ...] = (
    "/in/",            # personal profiles
    "/pub/",           # older public profile URLs
)

_LINKEDIN_EXCLUDED_PREFIXES: Tuple[str, ...] = (
    "/company/",
    "/school/",
    "/jobs/",
    "/feed/",
    "/groups/",
    "/learning/",
    "/posts/",
    "/events/",
    "/sales/",
    "/talent/",
    "/recruiter/",
    "/search/",
)

def _normalize_url(url: str) -> str:
    """
    Minimal URL normalization:
    - strip whitespace
    - remove trailing slash (except for scheme://host/)
    """
    u = (url or "").strip()
    if not u:
        return u
    # Remove trailing slash but keep "https://linkedin.com"
    if u.endswith("/") and len(u) > len("https://a.b/"):
        u = u[:-1]
    return u


def is_linkedin_profile_url(url: str) -> bool:
    """
    True only for LinkedIn *profile* URLs (not company pages, jobs, etc.).
    Accepts: linkedin.com/in/... and linkedin.com/pub/...
    """
    url = _normalize_url(url)
    if not url:
        return False

    try:
        parsed = urlparse(url)
    except Exception:
        return False

    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()

    # Must be LinkedIn domain
    if "linkedin.com" not in host:
        return False

    # Exclude obvious non-profile sections
    for excl in _LINKEDIN_EXCLUDED_PREFIXES:
        if path.startswith(excl):
            return False

    # Allow profile prefixes
    return any(path.startswith(p) for p in _LINKEDIN_ALLOWED_PATH_PREFIXES)


def filter_linkedin_profile_urls(urls: Iterable[str], *, unique: bool = True) -> List[str]:
    """
    Filters an iterable of URLs down to LinkedIn profile URLs only.
    Optionally de-duplicates while preserving order.
    """
    out: List[str] = []
    seen = set()

    for u in urls:
        u = _normalize_url(u)
        if not is_linkedin_profile_url(u):
            continue

        if unique:
            if u in seen:
                continue
            seen.add(u)

        out.append(u)

    return out


# -----------------------------
# Search client contract + retry
# -----------------------------

class SearchClient(ABC):
    """
    Interface/contract for search implementations.

    Implementations should:
    - accept SearchQuery (or accept query+params and create SearchQuery)
    - return a list of UrlHit ordered by rank (1..n)
    - raise SearchError on irrecoverable failures (optional but recommended)
    """

    @abstractmethod
    def search(self, q: SearchQuery) -> List[UrlHit]:
        """
        Execute a web search and return normalized hits (ranked).
        """
        raise NotImplementedError

    def search_with_retry(
        self,
        q: SearchQuery,
        *,
        attempts: int = 3,
        sleep_seconds: int = 30,
        retry_exceptions: Tuple[type[BaseException], ...] = (Exception,),
    ) -> List[UrlHit]:
        """
        Convenience wrapper matching your error-handling pattern:

            except Exception as e:
                print(...)
                time.sleep(30)

        Notes:
        - By default it retries on any Exception (configurable).
        - It prints attempt failures (simple and CLI-friendly).
        - On final failure it raises SearchRetriesExceeded.
        """
        if attempts < 1:
            raise ValueError("attempts must be >= 1")

        last_exc: Optional[BaseException] = None

        for attempt in range(attempts):
            try:
                return self.search(q)
            except retry_exceptions as e:
                last_exc = e
                # Match your current behavior
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt < attempts - 1:
                    time.sleep(sleep_seconds)

        raise SearchRetriesExceeded(
            f"Search failed after {attempts} attempts for query: {q.query}"
        ) from last_exc


def extract_urls(hits: Sequence[UrlHit], *, unique: bool = True) -> List[str]:
    """
    Helper: convert normalized hits into a list of URLs.
    """
    urls = [_normalize_url(h.url) for h in hits if _normalize_url(h.url)]
    if not unique:
        return urls

    out: List[str] = []
    seen = set()
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out
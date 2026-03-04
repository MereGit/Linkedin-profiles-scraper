"""
This module contains the functions used to filter out only the linkedin
profiles as the results
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Union
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode


class _HasUrl:
    url: str


# -----------------------------
# Rules
# -----------------------------

_ALLOWED_PROFILE_PREFIXES = ("/in/", "/pub/")

_EXCLUDED_PREFIXES = (
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

_ALLOWED_DOMAINS = (
    "linkedin.com",
    "www.linkedin.com",
    "it.linkedin.com",
)


"""
Normalize a LinkedIn URL for storage and deduplication.
@arg url(str): takes the url from the url list obtained from
the search
@returns a str without spaces, fragments or trailing slashes
"""

def normalize_linkedin_url(url: str) -> str:

    u = (url or "").strip()
    if not u:
        return ""

    try:
        parsed = urlparse(u)
    except Exception:
        return ""

    # If no scheme was provided, urlparse treats it as path. Try to fix lightly.
    if not parsed.netloc and parsed.path.startswith("www.linkedin.com"):
        parsed = urlparse("https://" + u)

    scheme = "https"
    netloc = parsed.netloc.lower()

    # Remove query params & fragments completely (tracking)
    path = parsed.path

    normalized = urlunparse((scheme, netloc, path, "", "", ""))

    # Remove trailing slash (but not if it's just domain)
    if normalized.endswith("/") and len(normalized) > len("https://a.b/"):
        normalized = normalized[:-1]

    return normalized


# -----------------------------
# Classification
# -----------------------------

"""
Verifies whether the input url is a linkedin profile.
@arg url(str): url from the list of results
@returns a bool that is 1 if the url is a linkedin profile
"""

def is_linkedin_profile_url(url: str) -> bool:

    u = normalize_linkedin_url(url)
    if not u:
        return False

    parsed = urlparse(u)
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()

    if not host.endswith("linkedin.com"):
        return False

    for excl in _EXCLUDED_PREFIXES:
        if path.startswith(excl):
            return False

    return any(path.startswith(p) for p in _ALLOWED_PROFILE_PREFIXES)



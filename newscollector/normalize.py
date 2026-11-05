"""URL canonicalization and fingerprints used for de-duplication."""

from __future__ import annotations

import hashlib
import html
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PREFIXES = ("utm_", "oly_", "_hs", "mc_", "vero_")
_TRACKING_KEYS = {"fbclid", "gclid", "dclid", "igshid", "ref", "ref_src", "cmpid", "ncid", "sref"}
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^\w]+", re.UNICODE)


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "https").lower()
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    for default in (":80", ":443"):
        if host.endswith(default):
            host = host[: -len(default)]
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith(_TRACKING_PREFIXES) and k.lower() not in _TRACKING_KEYS
    ]
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((scheme, host, path, urlencode(sorted(query)), ""))


def url_fingerprint(url: str) -> str:
    return hashlib.sha1(canonical_url(url).encode("utf-8")).hexdigest()


def normalize_title(title: str) -> str:
    text = html.unescape(_TAG_RE.sub("", title or ""))
    return _NON_WORD_RE.sub(" ", text).strip().lower()


def title_fingerprint(title: str) -> str:
    return hashlib.sha1(normalize_title(title).encode("utf-8")).hexdigest()


def clean_text(text: str, limit: int = 500) -> str:
    text = html.unescape(_TAG_RE.sub(" ", text or ""))
    text = _WS_RE.sub(" ", text).strip()
    return text[:limit]

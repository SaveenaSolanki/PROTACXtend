"""Small, dependency-free helpers shared across the package."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    """ISO-8601 UTC timestamp without timezone suffix (SQLite-sortable)."""
    return now_utc().replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def clamp01(value: float) -> float:
    if value is None:
        return 0.0
    try:
        x = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(x) or math.isinf(x):
        return 0.0
    return max(0.0, min(1.0, x))


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def days_between(earlier: str | None, later: datetime | None = None) -> float:
    start = parse_iso(earlier)
    if start is None:
        return 0.0
    end = later or now_utc()
    delta = end - start
    return max(0.0, delta.total_seconds() / 86400.0)


def iso_in_days(days: float) -> str:
    return (now_utc() + timedelta(days=days)).replace(microsecond=0).isoformat()


def dumps(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), default=str, sort_keys=True)


def loads(text: str | None, default: Any = None) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_text(text: str | None) -> str:
    """Lowercase, unicode-fold, collapse whitespace and punctuation."""
    if not text:
        return ""
    folded = unicodedata.normalize("NFKD", text)
    folded = folded.encode("ascii", "ignore").decode("ascii")
    folded = _WS.sub(" ", folded.lower()).strip()
    return folded


def content_hash(text: str | None) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()[:32]


def slug(text: str | None) -> str:
    return _NON_ALNUM.sub("-", normalize_text(text)).strip("-")


def tokenize(text: str | None) -> list[str]:
    return [t for t in _NON_ALNUM.split(normalize_text(text)) if len(t) > 1]


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def cosine(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def fts_query(text: str | None) -> str:
    """Build a safe FTS5 MATCH expression from free text.

    Tokens are OR-ed and each is quoted to avoid FTS5 syntax injection. Queries
    with no usable tokens return an empty string (caller should skip FTS).
    """
    toks = tokenize(text)
    if not toks:
        return ""
    return " OR ".join(f'"{t}"' for t in toks)

"""
Utility functions for deduplicating news articles by title.

Drop this file into your backend and use:

    from dedupe import dedupe_articles, dedupe_articles_fuzzy

Then, after aggregating articles from all your music/news APIs, call e.g.:

    articles = dedupe_articles_fuzzy(articles)

Each article is expected to be a dict with at least a "title" key.
"""

import re
from difflib import SequenceMatcher
from typing import Iterable, List, Dict, Any


def _normalize_title(title: str) -> str:
    """
    Normalize a headline so that cosmetic differences
    (punctuation, case, trailing pipes) don't matter.
    """
    if not title:
        return ""
    t = title.lower()

    # Remove things after a " | " (sites often add their brand like " | Billboard")
    t = t.split("|")[0]

    # Remove non-alphanumeric characters
    t = re.sub(r"[^a-z0-9\s]", " ", t)

    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()

    return t


def dedupe_articles(articles: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Simple de-duplication: keeps the first article seen for each
    *identical* normalized title.
    """
    seen = set()
    unique: List[Dict[str, Any]] = []

    for art in articles:
        title = art.get("title") or ""
        key = _normalize_title(title)

        if key in seen:
            continue

        seen.add(key)
        unique.append(art)

    return unique


def _similar(a: str, b: str, threshold: float = 0.86) -> bool:
    """
    Return True if two normalized titles are "similar enough"
    according to SequenceMatcher ratio.
    """
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= threshold


def dedupe_articles_fuzzy(
    articles: Iterable[Dict[str, Any]],
    threshold: float = 0.86,
) -> List[Dict[str, Any]]:
    """
    Fuzzy de-duplication: collapses articles whose normalized titles
    are very similar (not just identical).

    Example:
        "Donald Glover reveals he cancelled tour due to stroke"
        "Donald Glover discloses terrifying health issue that forced him to cancel tour"

    These will likely be merged into a single entry when using this function.
    """
    unique: List[Dict[str, Any]] = []

    for art in articles:
        raw_title = (art.get("title") or "").strip()
        norm = _normalize_title(raw_title)

        is_dup = False
        for kept in unique:
            kept_norm = kept.get("_norm_title", "")
            if _similar(norm, kept_norm, threshold=threshold):
                is_dup = True
                break

        if is_dup:
            continue

        # Make a shallow copy so we don't mutate caller's dicts
        art_copy = dict(art)
        art_copy["_norm_title"] = norm
        unique.append(art_copy)

    # Remove the helper field before returning
    for art in unique:
        art.pop("_norm_title", None)

    return unique

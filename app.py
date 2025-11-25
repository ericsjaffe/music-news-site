import os
from datetime import datetime
from typing import List, Dict, Any

import feedparser
from flask import Flask, render_template, request

from dedupe import dedupe_articles_fuzzy  # reuse your existing dedupe helper

app = Flask(__name__)

# Use Blabbermouth's main feed instead of the old FeedBurner URL
BLABBERMOUTH_RSS_URL = "https://blabbermouth.net/feed"

# Default image when a story has no usable image
DEFAULT_IMAGE_URL = "/static/default-music.png"


def parse_published(entry: Dict[str, Any]) -> str | None:
    """Normalize published/updated fields from the RSS entry into ISO 8601 string.
    If we can't parse, just return the raw string.
    """
    raw = entry.get("published") or entry.get("updated")
    if not raw:
        return None

    # feedparser often gives 'published_parsed' as a time.struct_time; we convert to ISO.
    if entry.get("published_parsed"):
        try:
            dt = datetime(*entry.published_parsed[:6])
            return dt.isoformat() + "Z"
        except Exception:
            pass

    return raw


def extract_image(entry: Dict[str, Any]) -> str:
    """Try a few common RSS media fields to find an image; fall back to default."""
    # 1) media:content or media:thumbnail
    media = entry.get("media_content") or entry.get("media_thumbnail")
    if media and isinstance(media, list):
        url = media[0].get("url")
        if url:
            return url

    # 2) enclosures (e.g. <enclosure url="..." type="image/jpeg">)
    enclosures = entry.get("enclosures")
    if enclosures and isinstance(enclosures, list):
        for enc in enclosures:
            url = enc.get("href") or enc.get("url")
            if url:
                return url

    # 3) fall back
    return DEFAULT_IMAGE_URL


def fetch_music_news(query: str | None = None, page_size: int = 40) -> List[Dict[str, Any]]:
    """
    Fetch latest heavy metal / hard rock news from Blabbermouth RSS.

    - Pull the feed with feedparser.
    - Optionally filter by a simple case-insensitive search on title + summary.
    - Normalize into the same article shape your template expects.
    - Apply fuzzy dedupe to avoid near-identical repeats.
    """
    feed = feedparser.parse(BLABBERMOUTH_RSS_URL)

    # Blabbermouth's feed sometimes has minor XML issues. feed.bozo=True just means
    # the parser saw *something* odd, but there may still be perfectly good entries.
    # Only error out if we truly have no entries at all.
    if not getattr(feed, "entries", None):
        if getattr(feed, "bozo", False):
            raise RuntimeError(f"Could not fetch Blabbermouth RSS feed: {feed.bozo_exception}")
        raise RuntimeError("Blabbermouth RSS feed returned no entries")

    entries = feed.entries

    articles: List[Dict[str, Any]] = []

    q_norm = (query or "").strip().lower()
    for entry in entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        link = entry.get("link")
        published_iso = parse_published(entry)
        image_url = extract_image(entry)

        # Optional search filter: if q is provided, require it in title or summary
        if q_norm:
            haystack = f"{title} {summary}".lower()
            if q_norm not in haystack:
                continue

        articles.append(
            {
                "title": title,
                "description": summary,
                "url": link,
                "image": image_url,
                "source": "Blabbermouth.net",
                "published_at": published_iso,
            }
        )

        if len(articles) >= page_size:
            break

    # De-duplicate by similar title/description (usually not necessary with a single feed,
    # but it helps if Blabbermouth republishes slightly tweaked headlines)
    articles = dedupe_articles_fuzzy(articles, threshold=0.85)

    return articles


@app.route("/")
def index():
    """
    Home page: shows latest heavy music news from Blabbermouth, optionally
    filtered by a search term (?q=...).
    """
    q = request.args.get("q")  # e.g. /?q=metallica
    articles: List[Dict[str, Any]] = []
    error: str | None = None

    try:
        articles = fetch_music_news(query=q)
    except Exception as e:
        error = str(e)

    # Format timestamps nicely for display
    for a in articles:
        if a["published_at"]:
            try:
                # If we stored ISO 8601 with 'Z'
                dt = datetime.fromisoformat(str(a["published_at"]).replace("Z", "+00:00"))
                a["published_at_human"] = dt.strftime("%b %d, %Y %I:%M %p")
            except Exception:
                a["published_at_human"] = a["published_at"]
        else:
            a["published_at_human"] = ""

    return render_template("index.html", articles=articles, error=error, query=q)


if __name__ == "__main__":
    # For local development; Render will use `gunicorn app:app`
    app.run(host="0.0.0.0", port=5000, debug=True)

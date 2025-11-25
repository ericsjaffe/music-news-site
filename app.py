import re
from html import unescape
from datetime import datetime
from typing import List, Dict, Any

import feedparser
from flask import Flask, render_template, request

from dedupe import dedupe_articles_fuzzy  # reuse your existing dedupe helper

app = Flask(__name__)

# Blabbermouth main RSS feed
BLABBERMOUTH_RSS_URL = "https://blabbermouth.net/feed"

# Default image when a story has no usable image
DEFAULT_IMAGE_URL = "/static/default-music.png"


def parse_published(entry: Dict[str, Any]) -> str | None:
    """Normalize published/updated fields into ISO 8601 if possible."""
    raw = entry.get("published") or entry.get("updated")
    if not raw:
        return None

    if entry.get("published_parsed"):
        try:
            dt = datetime(*entry.published_parsed[:6])
            return dt.isoformat() + "Z"
        except Exception:
            pass

    return raw


def image_from_html(html: str) -> str | None:
    """Pull the first <img src='...'> or <img src="..."> URL out of HTML."""
    if not html:
        return None
    # handle both single and double quotes
    match = re.search(r'<img[^>]+src=[\'\"]([^\'\"]+)[\'\"]', html, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def clean_html_summary(summary_html: str) -> str:
    """Strip HTML tags out of the RSS summary/content and collapse whitespace."""
    if not summary_html:
        return ""
    # Remove all tags
    text = re.sub(r"<[^>]+>", " ", summary_html)
    # Unescape HTML entities (&quot; -> ")
    text = unescape(text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_image(entry: Dict[str, Any]) -> str:
    """Try multiple locations to find a good image URL; fall back to default."""
    # 0) WordPress-style feeds often store HTML in content[0].value
    content_list = entry.get("content") or []
    if content_list and isinstance(content_list, list):
        value = content_list[0].get("value") or ""
        html_img = image_from_html(value)
        if html_img:
            return html_img

    # 1) summary_detail.value
    summary_detail = entry.get("summary_detail") or {}
    if isinstance(summary_detail, dict):
        html = summary_detail.get("value") or ""
        html_img = image_from_html(html)
        if html_img:
            return html_img

    # 2) plain summary
    summary_html = entry.get("summary") or ""
    html_img = image_from_html(summary_html)
    if html_img:
        return html_img

    # 3) media:content or media:thumbnail
    media = entry.get("media_content") or entry.get("media_thumbnail")
    if media and isinstance(media, list):
        url = media[0].get("url")
        if url:
            return url

    # 4) enclosures (e.g. <enclosure url="..." type="image/jpeg">)
    enclosures = entry.get("enclosures")
    if enclosures and isinstance(enclosures, list):
        for enc in enclosures:
            url = enc.get("href") or enc.get("url")
            if url:
                return url

    # 5) fall back
    return DEFAULT_IMAGE_URL


def fetch_music_news(query: str | None = None, page_size: int = 40) -> List[Dict[str, Any]]:
    """Fetch latest heavy music news from Blabbermouth RSS."""
    feed = feedparser.parse(BLABBERMOUTH_RSS_URL)

    # Only treat as fatal if there are no entries at all
    if not getattr(feed, "entries", None):
        if getattr(feed, "bozo", False):
            raise RuntimeError(f"Could not fetch Blabbermouth RSS feed: {feed.bozo_exception}")
        raise RuntimeError("Blabbermouth RSS feed returned no entries")

    entries = feed.entries
    articles: List[Dict[str, Any]] = []

    q_norm = (query or "").strip().lower()

    for entry in entries:
        # Prefer full content HTML if available for description text
        content_list = entry.get("content") or []
        if content_list and isinstance(content_list, list):
            raw_html = content_list[0].get("value") or ""
        else:
            raw_html = entry.get("summary", "")

        title = entry.get("title", "")
        summary_clean = clean_html_summary(raw_html)
        link = entry.get("link")
        published_iso = parse_published(entry)
        image_url = extract_image(entry)

        # Optional search filter: if q is provided, require it in title or summary text
        if q_norm:
            haystack = f"{title} {summary_clean}".lower()
            if q_norm not in haystack:
                continue

        articles.append(
            {
                "title": title,
                "description": summary_clean,
                "url": link,
                "image": image_url,
                "source": "Blabbermouth.net",
                "published_at": published_iso,
            }
        )

        if len(articles) >= page_size:
            break

    # De-duplicate similar headlines, just in case
    articles = dedupe_articles_fuzzy(articles, threshold=0.85)
    return articles


@app.route("/")
def index():
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
                dt = datetime.fromisoformat(str(a["published_at"]).replace("Z", "+00:00"))
                a["published_at_human"] = dt.strftime("%b %d, %Y %I:%M %p")
            except Exception:
                a["published_at_human"] = a["published_at"]
        else:
            a["published_at_human"] = ""

    return render_template("index.html", articles=articles, error=error, query=q)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

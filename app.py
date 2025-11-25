import os
from datetime import datetime, timedelta

import requests
from flask import Flask, render_template, request

from dedupe import dedupe_articles_fuzzy  # fuzzy dedupe for near-identical headlines

app = Flask(__name__)

# Read API key from environment
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

# Strongly music-specific keywords (used for filtering)
MUSIC_KEYWORDS_STRONG = [
    "music",
    "new music",
    "song",
    "new song",
    "single",
    "new single",
    "album",
    "new album",
    "ep",
    "lp",
    "track",
    "tracks",
    "mixtape",
    "remix",
    "music video",
    "music festival",
    "setlist",
    "concert",
    "live show",
    "headline show",
    "world tour",
    "tour dates",
    "grammy",
    "grammys",
    "billboard",
    "billboard hot 100",
    "chart",
    "top 40",
    "dj",
    "rapper",
    "band",
    "singer",
    "vocalist",
]

# Words that usually indicate a non-music story even if "tour" or similar appears
NON_MUSIC_BLOCKLIST = [
    "pga",
    "golf",
    "nfl",
    "nba",
    "mlb",
    "nhl",
    "premier league",
    "bundesliga",
    "serie a",
    "la liga",
    "f1",
    "formula 1",
    "grand prix",
    "nascar",
    "motogp",
    "cricket",
    "rugby",
    "tennis",
    "olympics",
    "world cup",
]

# Default image used when a story has no image
DEFAULT_IMAGE_URL = "/static/default-music.png"


def looks_like_music_article(article: dict) -> bool:
    """
    Return True only if the article clearly looks music-related.

    Strategy:
    - Work with lower‑cased title + description.
    - Immediately reject if any NON_MUSIC_BLOCKLIST term appears (sports, etc).
    - Require at least one MUSIC_KEYWORDS_STRONG term.
    """
    title = (article.get("title") or "").lower()
    desc = (article.get("description") or "").lower()
    text = f"{title} {desc}"

    if not text.strip():
        return False

    # Filter out obvious non‑music topics (sports, etc.)
    if any(block in text for block in NON_MUSIC_BLOCKLIST):
        return False

    # Must contain at least one strong music keyword
    return any(keyword in text for keyword in MUSIC_KEYWORDS_STRONG)


def fetch_music_news(query: str | None = None, page_size: int = 30) -> list[dict]:
    """
    Fetch latest music-related news using NewsAPI 'everything' endpoint,
    then filter to keep only clearly music-related articles.
    """
    if not NEWSAPI_KEY:
        raise RuntimeError("NEWSAPI_KEY environment variable is not set")

    base_url = "https://newsapi.org/v2/everything"

    # Default query focused on explicitly music-related content
    default_query = (
        '"new album" OR "new single" OR "new song" OR "music video" OR '
        '"debut album" OR "EP" OR "LP" OR "mixtape" OR '
        '"music festival" OR "world tour" OR concert OR "setlist" OR '
        'Grammy OR "Billboard Hot 100"'
    )
    final_query = query if query else default_query

    from_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

    params = {
        "q": final_query,
        "from": from_date,
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": page_size,
        "apiKey": NEWSAPI_KEY,
    }

    resp = requests.get(base_url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    raw_articles = data.get("articles", [])

    # Filter to only obviously music-related articles
    filtered = [a for a in raw_articles if looks_like_music_article(a)]

    cleaned: list[dict] = []
    for a in filtered:
        image_url = a.get("urlToImage") or DEFAULT_IMAGE_URL
        cleaned.append(
            {
                "title": a.get("title"),
                "description": a.get("description"),
                "url": a.get("url"),
                "image": image_url,
                "source": (a.get("source") or {}).get("name"),
                "published_at": a.get("publishedAt"),
            }
        )

    # Deduplicate very similar headlines (e.g. multiple versions of same story)
    cleaned = dedupe_articles_fuzzy(cleaned, threshold=0.86)

    return cleaned


@app.route("/")
def index():
    """
    Home page: shows latest music news, optionally filtered by a search term (?q=...).
    """
    q = request.args.get("q")  # e.g. /?q=hip-hop
    articles: list[dict] = []
    error: str | None = None

    try:
        articles = fetch_music_news(query=q)
    except Exception as e:
        # Surface any error (like missing API key) in the UI
        error = str(e)

    # Format timestamps nicely for display
    for a in articles:
        if a["published_at"]:
            try:
                dt = datetime.fromisoformat(a["published_at"].replace("Z", "+00:00"))
                a["published_at_human"] = dt.strftime("%b %d, %Y %I:%M %p")
            except Exception:
                a["published_at_human"] = a["published_at"]
        else:
            a["published_at_human"] = ""

    return render_template("index.html", articles=articles, error=error, query=q)


if __name__ == "__main__":
    # For local development; Render will use `gunicorn app:app`
    app.run(host="0.0.0.0", port=5000, debug=True)

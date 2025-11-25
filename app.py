import os
from datetime import datetime, timedelta

import requests
from flask import Flask, render_template, request

from dedupe import dedupe_articles, dedupe_articles_fuzzy

app = Flask(__name__)

# Read API key from environment
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

# Core music words that must be present somewhere in the title/description
MUSIC_CORE_KEYWORDS = [
    "music",
    "song",
    "single",
    "new single",
    "album",
    "new album",
    "ep",
    "e.p.",
    "lp",
    "track",
    "tracks",
    "mixtape",
    "playlist",
    "music video",
    "soundtrack",
    "studio version",
    "acoustic version",
]

# Extra music-ish context terms that we only accept if a core word is also present
MUSIC_CONTEXT_KEYWORDS = [
    "tour",
    "world tour",
    "tour dates",
    "live show",
    "headline show",
    "setlist",
    "concert",
    "festival",
    "headline slot",
    "dj",
    "rapper",
    "band",
    "singer",
    "vocalist",
    "producer",
    "grammy",
    "grammys",
    "billboard",
    "billboard hot 100",
    "chart",
    "top 40",
    "record deal",
    "label",
]

# Words that usually indicate a non-music story even if words like "tour" appear
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
    "mls",
    "college football",
    "college basketball",
]

# Default image when a story has no usable image
DEFAULT_IMAGE_URL = "/static/default-music.png"


def looks_like_music_article(article: dict) -> bool:
    """
    Return True only if the article clearly looks music-related.

    Rules (aggressive filter):
    1. Combine title + description, lowercase.
    2. If any NON_MUSIC_BLOCKLIST term appears -> reject.
    3. Require at least one MUSIC_CORE_KEYWORD.
       (So generic "tour" or "concert" alone is NOT enough.)
    """
    title = (article.get("title") or "").lower()
    desc = (article.get("description") or "").lower()
    text = f"{title} {desc}"

    if not text.strip():
        return False

    # Hard filter: exclude obvious non-music topics
    if any(block in text for block in NON_MUSIC_BLOCKLIST):
        return False

    # Must contain at least one core music word
    if any(core in text for core in MUSIC_CORE_KEYWORDS):
        return True

    # If nothing core appeared, treat it as non-music even if it mentions tours etc.
    return False


def fetch_music_news(query: str | None = None, page_size: int = 40) -> list[dict]:
    """
    Fetch latest music-related news using NewsAPI 'everything' endpoint,
    then filter to keep only clearly music-related articles and de-duplicate.
    """
    if not NEWSAPI_KEY:
        raise RuntimeError("NEWSAPI_KEY environment variable is not set")

    base_url = "https://newsapi.org/v2/everything"

    # Default query focused on explicitly music-related content.
    # We keep it fairly broad but still clearly music-ish.
    default_query = (
        '"new album" OR "new single" OR "new song" OR "music video" OR '
        '"debut album" OR "EP" OR "LP" OR mixtape OR '
        '"music festival" OR "world tour" OR concert OR setlist OR '
        'Grammy OR "Billboard Hot 100" OR "new track" OR "studio album"'
    )
    final_query = query if query else default_query

    # Only look at the last 7 days
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

    # First, filter to only obviously music-related articles
    filtered = [a for a in raw_articles if looks_like_music_article(a)]

    # Clean + normalize shape
    cleaned: list[dict] = []
    for a in filtered:
        image_url = a.get("urlToImage") or DEFAULT_IMAGE_URL
        cleaned.append(
            {
                "title": a.get("title") or "",
                "description": a.get("description") or "",
                "url": a.get("url"),
                "image": image_url,
                "source": (a.get("source") or {}).get("name"),
                "published_at": a.get("publishedAt"),
            }
        )

    # 1) Exact-title dedupe
    cleaned = dedupe_articles(cleaned)

    # 2) Fuzzy dedupe to collapse slightly different versions of same headline
    cleaned = dedupe_articles_fuzzy(cleaned, threshold=0.80)

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

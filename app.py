import os
from datetime import datetime, timedelta

import requests
from flask import Flask, render_template, request

app = Flask(__name__)

# Read API key from environment
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

# Words that strongly suggest the article is about music
MUSIC_KEYWORDS = [
    "music", "song", "single", "album", "ep", "lp", "track", "tracks",
    "mixtape", "remix", "setlist", "tour", "world tour", "concert",
    "gig", "festival", "band", "rapper", "rap", "hip-hop", "hip hop",
    "r&b", "rnb", "pop star", "dj", "producer", "singer", "vocalist",
    "grammy", "grammys", "billboard", "chart", "top 40"
]


def looks_like_music_article(article: dict) -> bool:
    """
    Return True only if the article's text clearly looks music-related.
    We check the title + description for any of the MUSIC_KEYWORDS.
    """
    title = (article.get("title") or "").lower()
    desc = (article.get("description") or "").lower()
    text = f"{title} {desc}"

    if not text.strip():
        return False

    return any(keyword in text for keyword in MUSIC_KEYWORDS)


def fetch_music_news(query: str | None = None, page_size: int = 30) -> list[dict]:
    """
    Fetch latest music-related news using NewsAPI 'everything' endpoint,
    then filter to keep only clearly music-related articles.
    """
    if not NEWSAPI_KEY:
        raise RuntimeError("NEWSAPI_KEY environment variable is not set")

    base_url = "https://newsapi.org/v2/everything"

    # Default query focused on music content
    default_query = (
        '"new album" OR "new single" OR "music video" OR '
        'song OR album OR artist OR band OR rapper OR singer OR '
        '"music festival" OR "world tour"'
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
        cleaned.append(
            {
                "title": a.get("title"),
                "description": a.get("description"),
                "url": a.get("url"),
                "image": a.get("urlToImage"),
                "source": (a.get("source") or {}).get("name"),
                "published_at": a.get("publishedAt"),
            }
        )
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

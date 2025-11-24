import os
import requests
from flask import Flask, render_template, request
from datetime import datetime, timedelta

app = Flask(__name__)

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

def fetch_music_news(query=None, page_size=30):
    """
    Fetch latest music-related news using NewsAPI 'everything' endpoint.
    """
    if not NEWSAPI_KEY:
        raise RuntimeError("NEWSAPI_KEY environment variable is not set")

    base_url = "https://newsapi.org/v2/everything"

    # Basic music-related query; you can tweak this
    default_query = '(music OR song OR album OR artist OR tour) AND NOT (stock OR bond OR crypto)'
    final_query = query if query else default_query

    # Optional: restrict to last 7 days so results are fresh
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

    articles = data.get("articles", [])
    cleaned = []
    for a in articles:
        cleaned.append({
            "title": a.get("title"),
            "description": a.get("description"),
            "url": a.get("url"),
            "image": a.get("urlToImage"),
            "source": (a.get("source") or {}).get("name"),
            "published_at": a.get("publishedAt"),
        })
    return cleaned


@app.route("/")
def index():
    # Optional keyword search from query string
    q = request.args.get("q")  # e.g., /?q=hip-hop
    articles = []
    error = None

    try:
        articles = fetch_music_news(query=q)
    except Exception as e:
        error = str(e)

    # Format timestamps nicely for the template
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
    app.run(debug=True)

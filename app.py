import re
import time
from html import unescape
from datetime import datetime
from typing import List, Dict, Any
from urllib.parse import quote_plus

import feedparser
import requests
from flask import Flask, render_template, request

from dedupe import dedupe_articles_fuzzy
from cache_db import init_db, get_cached_results, save_cached_results, cleanup_old_cache
  # reuse your existing dedupe helper

app = Flask(__name__)

# Initialize cache database
init_db()

# Loudwire main RSS feed
LOUDWIRE_LATEST_FEED = "http://loudwire.com/category/news/feed"

# Default image when a story has no usable image
DEFAULT_IMAGE_URL = "/static/default-music.png"

# MusicBrainz API settings
API_BASE = "https://musicbrainz.org/ws/2/release"
USER_AGENT = "EricMusicDateFinder/1.0 (eric.s.jaffe@gmail.com)"
MAX_YEARS_PER_REQUEST = 25


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
    """Fetch latest heavy music news from Loudwire RSS.
    If query provided, search via Loudwire's search RSS to get more relevant results.
    """
    q_norm = (query or "").strip().lower()
    
    # If there's a search query, use Loudwire's search feed for better results
    if q_norm:
        # Loudwire search RSS URL
        search_url = f"https://loudwire.com/?s={quote_plus(query)}&feed=rss2"
        feed = feedparser.parse(search_url)
    else:
        # Use main news feed for browsing
        feed = feedparser.parse(LOUDWIRE_LATEST_FEED)

    # Only treat as fatal if there are no entries at all
    if not getattr(feed, "entries", None):
        if getattr(feed, "bozo", False):
            raise RuntimeError(f"Could not fetch Loudwire RSS feed: {feed.bozo_exception}")
        raise RuntimeError("Loudwire RSS feed returned no entries")

    entries = feed.entries
    articles: List[Dict[str, Any]] = []

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

        articles.append(
            {
                "title": title,
                "description": summary_clean,
                "url": link,
                "image": image_url,
                "source": "Loudwire",
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


def search_releases_for_date(year: int, mm_dd: str, limit: int = 50):
    """
    Call MusicBrainz search:
      /ws/2/release/?query=date:YYYY-MM-DD&fmt=json&limit=...
    Returns list of releases (dicts).
    """
    ymd = f"{year}-{mm_dd}"  # e.g. 2019-11-22
    params = {
        "query": f"date:{ymd}",
        "fmt": "json",
        "limit": str(limit),
    }
    headers = {
        "User-Agent": USER_AGENT,
    }

    resp = requests.get(API_BASE, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("releases", [])


@app.route("/releases", methods=["GET", "POST"])
def releases():
    """Find music releases on a specific date across multiple years."""
    error = None
    results = None
    current_year = datetime.now().year
    today = datetime.now()

    # Defaults for first load / GET - use today's date and last 20 years
    date_value = today.strftime("%Y-%m-%d")
    start_year = current_year - 20  # Last 20 years to stay under the 25 year limit
    end_year = current_year
    pretty_date = today.strftime("%B %d")
    mm_dd = today.strftime("%m-%d")
    
    # Auto-load results on first visit (GET request)
    should_fetch = request.method == "GET"

    if request.method == "POST":
        # Get form values
        date_value = request.form.get("date", "").strip()
        start_str = request.form.get("start_year", "").strip()
        end_str = request.form.get("end_year", "").strip()

        # Parse date
        try:
            _dt = datetime.strptime(date_value, "%Y-%m-%d")
            mm_dd = date_value[5:]  # "YYYY-MM-DD" -> "MM-DD"
            pretty_date = _dt.strftime("%B %d")  # e.g. "November 22"
        except ValueError:
            error = "Invalid date. Please use the date picker."
            mm_dd = None

        # Parse years with defaults
        try:
            start_year = int(start_str) if start_str else 1990
            end_year = int(end_str) if end_str else current_year
            if end_year < start_year:
                start_year, end_year = end_year, start_year
        except ValueError:
            error = (error + " | " if error else "") + "Start/end year must be numbers."
            start_year = 2000
            end_year = current_year
        
        should_fetch = True

    # Check cache first
    if should_fetch and not error and mm_dd:
        cached = get_cached_results(mm_dd, start_year, end_year)
        if cached:
            # Convert cached dicts back to Release objects
            results = []
            for r in cached:
                results.append(
                    type("Release", (object,), {
                        "year": r["year"],
                        "title": r["title"],
                        "artist": r["artist"],
                        "date": r["date"],
                        "url": r["url"],
                        "cover_art": r.get("cover_art"),
                    })
                )
            # Skip the API calls, we have cached data
            should_fetch = False
    
        # Clamp the range so we don't time out
    if should_fetch and not error and mm_dd:
        year_span = end_year - start_year + 1
        if year_span > MAX_YEARS_PER_REQUEST:
            original_end = end_year
            end_year = start_year + MAX_YEARS_PER_REQUEST - 1
            if end_year > current_year:
                end_year = current_year
            error = (error + " | " if error else "") + (
                f"Year range too large ({year_span} years). "
                f"Showing only {start_year}–{end_year}. "
                f"Try smaller chunks like 1990–2010, then 2011–{current_year}."
            )

        results = []
        for year in range(start_year, end_year + 1):
            try:
                releases = search_releases_for_date(year, mm_dd, limit=50)
            except requests.HTTPError as e:
                error = f"HTTP error for year {year}: {e}"
                break
            except Exception as e:
                error = f"Error for year {year}: {e}"
                break

            for r in releases:
                title = r.get("title")
                date = r.get("date")
                artist = None
                ac = r.get("artist-credit") or []
                if ac and isinstance(ac, list) and "name" in ac[0]:
                    artist = ac[0]["name"]
                mbid = r.get("id")
                url = f"https://musicbrainz.org/release/{mbid}" if mbid else None
                
                # Try to get cover art from Cover Art Archive
                cover_art = None
                if mbid:
                    cover_art = f"https://coverartarchive.org/release/{mbid}/front-250"

                # use a tiny object so template can do r.year, r.title, etc.
                results.append(
                    type("Release", (object,), {
                        "year": year,
                        "title": title,
                        "artist": artist,
                        "date": date,
                        "url": url,
                        "cover_art": cover_art,
                    })
                )

            # Be polite with MusicBrainz but not too slow
            time.sleep(0.1)

        # Sort nicely
        if results:
            results.sort(key=lambda x: (-x.year, x.artist or "", x.title or ""))

            # Save to cache for future requests
            cache_data = [
                {
                    "year": r.year,
                    "title": r.title,
                    "artist": r.artist,
                    "date": r.date,
                    "url": r.url,
                    "cover_art": r.cover_art
                }
                for r in results
            ]
            save_cached_results(mm_dd, start_year, end_year, cache_data)

    return render_template(
        "releases.html",
        error=error,
        results=results,
        date_value=date_value,
        start_year=start_year,
        end_year=end_year,
        pretty_date=pretty_date or "",
        current_year=current_year,
    )




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)


@app.route("/sitemap.xml")
def sitemap():
    """Generate dynamic sitemap.xml with all pages."""
    from flask import make_response
    
    # Get your actual domain
    domain = request.host_url.rstrip("/")
    
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{domain}/</loc>
    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>{domain}/releases</loc>
    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
</urlset>"""
    
    response = make_response(xml)
    response.headers["Content-Type"] = "application/xml"
    return response


@app.route("/robots.txt")
def robots():
    """Generate robots.txt file."""
    from flask import make_response
    
    # Get your actual domain
    domain = request.host_url.rstrip("/")
    
    txt = f"""User-agent: *
Allow: /
Disallow: /static/

Sitemap: {domain}/sitemap.xml
"""
    
    response = make_response(txt)
    response.headers["Content-Type"] = "text/plain"
    return response


@app.route("/article")
def article():
    """Proxy page to display article content without leaving the site."""
    from urllib.parse import unquote
    from bs4 import BeautifulSoup
    
    url = request.args.get("url")
    if not url:
        return "No article URL provided", 400
    
    try:
        # Fetch the article page
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title
        title_tag = soup.find('h1', class_='entry-title') or soup.find('h1') or soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else "Article"
        
        # Extract published date
        time_tag = soup.find('time') or soup.find('span', class_='date')
        published_at = time_tag.get_text(strip=True) if time_tag else None
        
        # Extract main image
        img_tag = soup.find('meta', property='og:image')
        if not img_tag:
            img_tag = soup.find('img', class_='wp-post-image') or soup.find('article').find('img') if soup.find('article') else None
        image = img_tag.get('content') if img_tag and img_tag.has_attr('content') else (img_tag.get('src') if img_tag else None)
        
        # Extract article content
        article_body = soup.find('div', class_='entry-content') or soup.find('article') or soup.find('main')
        
        if article_body:
            # Remove unwanted elements
            for element in article_body.find_all(['script', 'style', 'iframe', 'nav', 'aside', 'footer', 'h1', 'h2']):
                element.decompose()
            
            # Keep the first image as featured image, remove the rest
            images = article_body.find_all('img')
            if images and not image:
                # Use first image from content as featured image if we don't have one
                image = images[0].get('src')
            
            # Now remove all images from content
            for img in images:
                img.decompose()
            
            # Get clean HTML
            content = str(article_body)
        else:
            content = "<p>Could not extract article content.</p>"
        
        return render_template(
            "article.html",
            title=title,
            content=content,
            image=image,
            published_at=published_at,
            source="Loudwire",
            source_url=url
        )
        
    except Exception as e:
        return f"Error loading article: {str(e)}", 500

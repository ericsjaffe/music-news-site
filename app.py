import re
import time
import os
import sqlite3
from html import unescape
from datetime import datetime
from typing import List, Dict, Any
from urllib.parse import quote_plus
from flask import Flask, render_template, request, make_response
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from dotenv import load_dotenv
import threading

# Load environment variables
load_dotenv()

import feedparser
import requests

# Try to import SendGrid for email sending (preferred for Render)
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    print("Warning: SendGrid not installed. Email features may not work on Render.")

from dedupe import dedupe_articles_fuzzy
from cache_db import init_db, get_cached_results, save_cached_results, cleanup_old_cache
from newsletter_db import (
    init_newsletter_db, 
    add_subscriber, 
    confirm_subscriber, 
    get_subscriber_count,
    unsubscribe
)
from sms_db import (
    init_sms_db,
    add_sms_subscriber,
    confirm_sms_subscriber,
    get_all_confirmed_sms_subscribers,
    unsubscribe_sms,
    get_sms_subscriber_count,
    article_already_sent,
    mark_article_sent
)

try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    print("Warning: Twilio not installed. SMS features disabled. Run: pip install twilio")

app = Flask(__name__)

# Initialize databases
init_db()
init_newsletter_db()
init_sms_db()

# Email configuration (optional - configure for production)
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY', '')
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USERNAME = os.getenv('SMTP_USERNAME', 'your-email@gmail.com')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', 'your-app-password')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'noreply@musichub.com')

# Admin notification email
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'eric.s.jaffe@gmail.com')

# Twilio SMS Configuration (configure these to enable SMS)
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', 'your-account-sid')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', 'your-auth-token')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '+1234567890')
ADMIN_PHONE = os.getenv('ADMIN_PHONE', '+12154319224')

# Loudwire main RSS feed
LOUDWIRE_LATEST_FEED = "https://loudwire.com/category/news/feed"

# Default image when a story has no usable image
DEFAULT_IMAGE_URL = "/static/default-music.png"

# MusicBrainz API settings
API_BASE = "https://musicbrainz.org/ws/2/release"
USER_AGENT = "EricMusicDateFinder/1.0 (eric.s.jaffe@gmail.com)"
MAX_YEARS_PER_REQUEST = 25

# Genre keywords for filtering
GENRE_KEYWORDS = {
    "rock": ["rock", "hard rock", "classic rock", "punk rock"],
    "metal": ["metal", "heavy metal", "death metal", "black metal", "thrash metal", "metalcore", "nu-metal"],
    "pop": ["pop", "pop music", "synth-pop", "indie pop"],
    "hip-hop": ["hip-hop", "hip hop", "rap", "rapper"],
    "country": ["country", "country music", "americana"],
    "electronic": ["electronic", "edm", "techno", "house", "dubstep"],
    "indie": ["indie", "indie rock", "indie music", "alternative"],
    "jazz": ["jazz", "jazz music"],
    "blues": ["blues", "blues rock"],
    "punk": ["punk", "punk rock", "hardcore punk"]
}

# Trending article views (in-memory cache for demo)
trending_views = {}

# Artist image cache
artist_image_cache = {}

# LastFM API key (free tier - get from https://www.last.fm/api)
LASTFM_API_KEY = "YOUR_LASTFM_API_KEY_HERE"  # Users can add their own


def get_artist_image(artist_name: str) -> str | None:
    """Fetch artist image from Last.fm API."""
    if artist_name in artist_image_cache:
        return artist_image_cache[artist_name]
    
    if LASTFM_API_KEY == "YOUR_LASTFM_API_KEY_HERE":
        return None  # Skip if no API key configured
    
    try:
        url = f"http://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist={quote_plus(artist_name)}&api_key={LASTFM_API_KEY}&format=json"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if "artist" in data and "image" in data["artist"]:
            # Get largest image
            images = data["artist"]["image"]
            for img in reversed(images):
                if img.get("#text"):
                    artist_image_cache[artist_name] = img["#text"]
                    return img["#text"]
    except Exception as e:
        print(f"Error fetching artist image: {e}")
    
    return None


def extract_youtube_id(text: str) -> str | None:
    """Extract YouTube video ID from text."""
    patterns = [
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def get_spotify_search_url(artist: str, track: str = "") -> str:
    """Generate Spotify search URL."""
    query = f"{artist} {track}".strip()
    return f"https://open.spotify.com/search/{quote_plus(query)}"


def get_apple_music_search_url(artist: str, track: str = "") -> str:
    """Generate Apple Music search URL."""
    query = f"{artist} {track}".strip()
    return f"https://music.apple.com/us/search?term={quote_plus(query)}"


def send_confirmation_email(email: str, token: str, base_url: str = None) -> bool:
    """Send confirmation email to subscriber."""
    try:
        # Generate confirmation link
        if base_url is None:
            base_url = request.host_url
        confirmation_url = f"{base_url}newsletter/confirm/{token}"
        
        subject = "Confirm your Music Hub Newsletter Subscription"
        
        # Plain text version
        text = f"""
Thanks for subscribing to Music Hub Newsletter!

Please confirm your subscription by clicking the link below:
{confirmation_url}

If you didn't sign up for this newsletter, you can safely ignore this email.

- Music Hub Team
"""
        
        # HTML version
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #ec4899, #fb7185); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }}
        .button {{ display: inline-block; background: #ec4899; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
        .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎵 Welcome to Music Hub!</h1>
        </div>
        <div class="content">
            <p>Thanks for subscribing to the Music Hub Newsletter!</p>
            <p>You're one step away from getting the latest music news delivered straight to your inbox.</p>
            <p style="text-align: center;">
                <a href="{confirmation_url}" class="button">Confirm Your Subscription</a>
            </p>
            <p><small>If the button doesn't work, copy and paste this link into your browser:</small><br>
            <small>{confirmation_url}</small></p>
            <p><small>If you didn't sign up for this newsletter, you can safely ignore this email.</small></p>
        </div>
        <div class="footer">
            <p>Music Hub - Your source for the latest music news</p>
        </div>
    </div>
</body>
</html>
"""
        
        # Try SendGrid first (works on Render), fallback to SMTP
        if SENDGRID_AVAILABLE and SENDGRID_API_KEY:
            print(f"Attempting to send confirmation email to {email} via SendGrid")
            message = Mail(
                from_email=Email(SMTP_USERNAME if SMTP_USERNAME != "your-email@gmail.com" else "noreply@musichub.com", "Music Hub"),
                to_emails=To(email),
                subject=subject,
                plain_text_content=Content("text/plain", text),
                html_content=Content("text/html", html)
            )
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            response = sg.send(message)
            print(f"✅ Confirmation email sent successfully to {email} via SendGrid (status: {response.status_code})")
            return True
        
        # Fallback to SMTP (for local development)
        elif SMTP_USERNAME != "your-email@gmail.com":
            print(f"Attempting to send confirmation email to {email} via SMTP {SMTP_SERVER}:{SMTP_PORT}")
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = FROM_EMAIL
            msg['To'] = email
            
            part1 = MIMEText(text, 'plain')
            part2 = MIMEText(html, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)
            
            print(f"✅ Confirmation email sent successfully to {email} via SMTP")
            return True
        else:
            print(f"⚠️  Email confirmation skipped (no email service configured). Token: {token}")
            return False
        
        print(f"✅ Confirmation email sent successfully to {email}")
        return True
    except Exception as e:
        print(f"❌ Error sending confirmation email to {email}: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_admin_notification(email: str) -> bool:
    """Send notification to admin when someone subscribes."""
    if SMTP_USERNAME == "your-email@gmail.com" and not (SENDGRID_AVAILABLE and SENDGRID_API_KEY):
        print(f"Admin notification skipped (no email service configured). New subscriber: {email}")
        return True
    
    try:
        subject = "🎵 New Music Hub Newsletter Subscriber"
        
        text = f"""
New subscriber signed up for the Music Hub Newsletter!

Email: {email}
Time: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}

View all subscribers: https://music-news-site.onrender.com/admin/subscribers
"""
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }}
        .subscriber {{ background: white; padding: 15px; border-left: 4px solid #667eea; margin: 20px 0; }}
        .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎵 New Subscriber!</h1>
        </div>
        <div class="content">
            <p>Great news! Someone just signed up for your Music Hub Newsletter.</p>
            
            <div class="subscriber">
                <strong>Email:</strong> {email}<br>
                <strong>Time:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
            </div>
            
            <p>They'll receive a confirmation email shortly.</p>
            
            <div class="footer">
                <p>Music Hub Newsletter System</p>
            </div>
        </div>
    </div>
</body>
</html>
"""
        
        # Try SendGrid first (works on Render)
        if SENDGRID_AVAILABLE and SENDGRID_API_KEY:
            message = Mail(
                from_email=Email(SMTP_USERNAME if SMTP_USERNAME != "your-email@gmail.com" else "noreply@musichub.com", "Music Hub"),
                to_emails=To(ADMIN_EMAIL),
                subject=subject,
                plain_text_content=Content("text/plain", text),
                html_content=Content("text/html", html)
            )
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            response = sg.send(message)
            print(f"✅ Admin notification sent via SendGrid (status: {response.status_code})")
            return True
        
        # Fallback to SMTP (for local development)
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL
        msg['To'] = ADMIN_EMAIL
        
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        msg.attach(part1)
        msg.attach(part2)
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        
        return True
    except Exception as e:
        print(f"Error sending admin notification: {e}")
        return False


def send_sms_confirmation(phone_number: str, token: str) -> bool:
    """Send SMS confirmation to subscriber."""
    if not TWILIO_AVAILABLE:
        print(f"SMS confirmation skipped (Twilio not installed). Token: {token}")
        return True
    
    if TWILIO_ACCOUNT_SID == "your-account-sid":
        print(f"SMS confirmation skipped (Twilio not configured). Token: {token}")
        return True
    
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        confirmation_url = f"{request.host_url}sms/confirm/{token}"
        
        message = client.messages.create(
            body=f"🎵 Music Hub: Confirm your SMS subscription by visiting: {confirmation_url}\n\nReply STOP to unsubscribe anytime.",
            from_=TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        
        print(f"SMS confirmation sent: {message.sid}")
        return True
    except Exception as e:
        print(f"Error sending SMS confirmation: {e}")
        return False


def send_article_sms_notification(article_title: str, article_url: str):
    """Send SMS notification about new article to all confirmed subscribers."""
    if not TWILIO_AVAILABLE:
        print("SMS notifications skipped (Twilio not installed)")
        return
    
    if TWILIO_ACCOUNT_SID == "your-account-sid":
        print("SMS notifications skipped (Twilio not configured)")
        return
    
    # Check if already sent
    if article_already_sent(article_url):
        print(f"SMS notification already sent for: {article_title}")
        return
    
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        subscribers = get_all_confirmed_sms_subscribers()
        
        if not subscribers:
            print("No SMS subscribers to notify")
            return
        
        # Truncate title if too long
        short_title = article_title[:100] + "..." if len(article_title) > 100 else article_title
        full_url = f"{request.host_url}article?url={article_url}"
        
        message_body = f"🎵 New on Music Hub:\n\n{short_title}\n\nRead more: {full_url}\n\nReply STOP to unsubscribe"
        
        sent_count = 0
        for _, phone_number, _, _ in subscribers:
            try:
                message = client.messages.create(
                    body=message_body,
                    from_=TWILIO_PHONE_NUMBER,
                    to=phone_number
                )
                print(f"SMS sent to {phone_number}: {message.sid}")
                sent_count += 1
                time.sleep(1)  # Rate limiting
            except Exception as e:
                print(f"Error sending SMS to {phone_number}: {e}")
        
        # Mark as sent
        mark_article_sent(article_url, sent_count)
        print(f"Article notification sent to {sent_count} subscribers")
        
    except Exception as e:
        print(f"Error sending article SMS notifications: {e}")


def send_admin_sms_notification(phone_number: str) -> bool:
    """Send SMS to admin when someone subscribes."""
    if not TWILIO_AVAILABLE or TWILIO_ACCOUNT_SID == "your-account-sid":
        print(f"Admin SMS notification skipped. New subscriber: {phone_number}")
        return True
    
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        message = client.messages.create(
            body=f"🎵 Music Hub: New SMS subscriber!\n\n{phone_number}\n\nTime: {datetime.now().strftime('%I:%M %p')}",
            from_=TWILIO_PHONE_NUMBER,
            to=ADMIN_PHONE
        )
        
        print(f"Admin SMS sent: {message.sid}")
        return True
    except Exception as e:
        print(f"Error sending admin SMS: {e}")
        return False


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


def detect_genres(text: str) -> List[str]:
    """Detect genres mentioned in article text."""
    text_lower = text.lower()
    detected = []
    for genre, keywords in GENRE_KEYWORDS.items():
        if any(keyword in text_lower for keyword in keywords):
            detected.append(genre)
    return detected


def extract_artist_from_title(title: str) -> str | None:
    """Try to extract artist name from article title."""
    # Common patterns: "Artist Name Does Something" or "Artist Name: Something"
    # This is a simple heuristic
    patterns = [
        r"^([A-Z][a-zA-Z\s&'-]+?)(?:\s+(?:Announces?|Releases?|Drops?|Shares?|Unveils?|Says?|Talks?|Discusses?))",
        r"^([A-Z][a-zA-Z\s&'-]+?):",
        r"^([A-Z][a-zA-Z\s&'-]+?)\s+-\s+",
    ]
    for pattern in patterns:
        match = re.match(pattern, title)
        if match:
            return match.group(1).strip()
    return None


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
    If query provided, filter results by search term.
    """
    q_norm = (query or "").strip().lower()
    
    # Always use the main news feed (search RSS is not working reliably)
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

        # Detect genres and artist
        combined_text = f"{title} {summary_clean}"
        genres = detect_genres(combined_text)
        artist = extract_artist_from_title(title)
        
        # If there's a search query, filter by title and description
        if q_norm:
            title_lower = title.lower()
            desc_lower = summary_clean.lower()
            if q_norm not in title_lower and q_norm not in desc_lower:
                continue  # Skip articles that don't match the search query

        articles.append(
            {
                "title": title,
                "description": summary_clean,
                "url": link,
                "image": image_url,
                "source": "Loudwire",
                "published_at": published_iso,
                "genres": genres,
                "artist": artist,
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
    genre_filter = request.args.get("genre")  # e.g. /?genre=metal
    view = request.args.get("view", "all")  # all, trending
    articles: List[Dict[str, Any]] = []
    error: str | None = None

    try:
        articles = fetch_music_news(query=q)
        
        # Apply genre filter if specified
        if genre_filter:
            articles = [a for a in articles if genre_filter in a.get("genres", [])]
        
        # Track views for trending
        for article in articles:
            url = article.get("url")
            if url:
                trending_views[url] = trending_views.get(url, 0) + 0.1  # Small increment for view
        
        # Sort by trending if requested
        if view == "trending":
            articles = sorted(articles, key=lambda a: trending_views.get(a.get("url"), 0), reverse=True)
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

    # Get all unique genres from articles
    all_genres = sorted(set(g for a in articles for g in a.get("genres", [])))
    
    return render_template(
        "index.html", 
        articles=articles, 
        error=error, 
        query=q,
        genre_filter=genre_filter,
        all_genres=all_genres,
        view=view,
        available_genres=list(GENRE_KEYWORDS.keys())
    )


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

    # Defaults for first load / GET - use today's date and last 15 years
    date_value = today.strftime("%Y-%m-%d")
    start_year = current_year - 15  # Last 15 years
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
        # Iterate in reverse to fetch newest years first
        for year in range(end_year, start_year - 1, -1):
            try:
                releases = search_releases_for_date(year, mm_dd, limit=50)
            except (requests.HTTPError, requests.ConnectionError, ConnectionResetError) as e:
                # Skip this year and continue with others
                print(f"Skipping year {year} due to connection issue: {e}")
                continue
            except Exception as e:
                # For other errors, skip and continue
                print(f"Skipping year {year} due to error: {e}")
                continue

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

        # Sort by year (newest first), then by artist, then by title
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


@app.route("/release/<mbid>")
def release_detail(mbid):
    """Display detailed information about a specific release."""
    try:
        # Fetch release details from MusicBrainz API
        headers = {"User-Agent": USER_AGENT}
        
        # Get release info with recordings and artist credits
        release_url = f"https://musicbrainz.org/ws/2/release/{mbid}"
        params = {
            "fmt": "json",
            "inc": "artists+labels+recordings+release-groups+media"
        }
        
        response = requests.get(release_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        release_data = response.json()
        
        # Extract basic info
        title = release_data.get("title", "Unknown Title")
        date = release_data.get("date", "Unknown Date")
        
        # Get artist(s)
        artist_credits = release_data.get("artist-credit", [])
        artists = []
        for ac in artist_credits:
            if isinstance(ac, dict) and "name" in ac:
                artists.append(ac["name"])
        artist_name = ", ".join(artists) if artists else "Unknown Artist"
        
        # Get label info
        labels = []
        label_info = release_data.get("label-info", [])
        for li in label_info:
            if isinstance(li, dict) and "label" in li:
                label = li["label"]
                if isinstance(label, dict) and "name" in label:
                    catalog = li.get("catalog-number", "")
                    label_str = f"{label['name']}"
                    if catalog:
                        label_str += f" ({catalog})"
                    labels.append(label_str)
        
        # Get format and track count
        media = release_data.get("media", [])
        formats = []
        total_tracks = 0
        tracklist = []
        
        for medium in media:
            format_name = medium.get("format", "Digital Media")
            track_count = medium.get("track-count", 0)
            formats.append(f"{format_name}")
            total_tracks += track_count
            
            # Get tracks for this medium
            tracks = medium.get("tracks", [])
            for track in tracks:
                track_number = track.get("position", "?")
                track_title = track.get("title", "Unknown Track")
                
                # Get track length if available
                length_ms = track.get("length")
                duration = ""
                if length_ms:
                    seconds = length_ms // 1000
                    minutes = seconds // 60
                    secs = seconds % 60
                    duration = f"{minutes}:{secs:02d}"
                
                tracklist.append({
                    "number": track_number,
                    "title": track_title,
                    "duration": duration
                })
        
        # Get cover art
        cover_art = f"https://coverartarchive.org/release/{mbid}/front-500"
        
        # Get release group ID for genre/type info
        release_group = release_data.get("release-group", {})
        primary_type = release_group.get("primary-type", "Album")
        
        # Build Spotify and Apple Music search links
        search_query = f"{artist_name} {title}".replace(" ", "+")
        spotify_url = f"https://open.spotify.com/search/{search_query}"
        apple_music_url = f"https://music.apple.com/us/search?term={search_query}"
        
        return render_template(
            "release_detail.html",
            mbid=mbid,
            title=title,
            artist=artist_name,
            date=date,
            labels=labels,
            formats=formats,
            total_tracks=total_tracks,
            tracklist=tracklist,
            cover_art=cover_art,
            primary_type=primary_type,
            spotify_url=spotify_url,
            apple_music_url=apple_music_url,
            musicbrainz_url=f"https://musicbrainz.org/release/{mbid}"
        )
        
    except requests.HTTPError as e:
        return render_template(
            "error.html",
            error_title="Release Not Found",
            error_message=f"Could not fetch release information from MusicBrainz: {str(e)}"
        ), 404
    except Exception as e:
        return render_template(
            "error.html",
            error_title="Error Loading Release",
            error_message=f"An error occurred: {str(e)}"
        ), 500


@app.route("/artist/<artist_name>")
def artist_page(artist_name):
    """Show articles related to a specific artist."""
    articles: List[Dict[str, Any]] = []
    error: str | None = None
    
    try:
        # Fetch all news and filter by artist
        all_articles = fetch_music_news()
        articles = [a for a in all_articles if a.get("artist") and artist_name.lower() in a.get("artist", "").lower()]
        
        # Also search by artist name in title/description if no artist match
        if not articles:
            articles = [a for a in all_articles if artist_name.lower() in a.get("title", "").lower() 
                       or artist_name.lower() in a.get("description", "").lower()]
    except Exception as e:
        error = str(e)
    
    # Format timestamps
    for a in articles:
        if a["published_at"]:
            try:
                dt = datetime.fromisoformat(str(a["published_at"]).replace("Z", "+00:00"))
                a["published_at_human"] = dt.strftime("%b %d, %Y %I:%M %p")
            except Exception:
                a["published_at_human"] = a["published_at"]
        else:
            a["published_at_human"] = ""
    
    # Get artist image
    artist_image = get_artist_image(artist_name)
    
    # Generate music service links
    spotify_url = get_spotify_search_url(artist_name)
    apple_music_url = get_apple_music_search_url(artist_name)
    
    # Extract YouTube video if present in any article
    youtube_id = None
    for article in articles:
        combined_text = f"{article.get('title', '')} {article.get('description', '')}"
        youtube_id = extract_youtube_id(combined_text)
        if youtube_id:
            break
    
    return render_template(
        "artist.html", 
        artist_name=artist_name, 
        articles=articles, 
        error=error,
        artist_image=artist_image,
        spotify_url=spotify_url,
        apple_music_url=apple_music_url,
        youtube_id=youtube_id
    )


@app.route("/touring")
def touring():
    """Touring page - coming soon."""
    return render_template("touring.html")


@app.route("/videos")
def videos():
    """Videos page - coming soon."""
    return render_template("videos.html")


@app.route("/merch")
def merch():
    """Merch page - coming soon."""
    return render_template("merch.html")


@app.route("/api/load-more")
def load_more():
    """API endpoint for infinite scroll - returns JSON of articles."""
    offset = int(request.args.get("offset", 0))
    limit = int(request.args.get("limit", 20))
    genre = request.args.get("genre")
    
    try:
        all_articles = fetch_music_news(page_size=100)
        
        # Apply genre filter if specified
        if genre:
            all_articles = [a for a in all_articles if genre in a.get("genres", [])]
        
        # Paginate
        paginated = all_articles[offset:offset+limit]
        
        # Format timestamps
        for a in paginated:
            if a["published_at"]:
                try:
                    dt = datetime.fromisoformat(str(a["published_at"]).replace("Z", "+00:00"))
                    a["published_at_human"] = dt.strftime("%b %d, %Y %I:%M %p")
                except Exception:
                    a["published_at_human"] = a["published_at"]
            else:
                a["published_at_human"] = ""
        
        return {"articles": paginated, "has_more": offset + limit < len(all_articles)}
    except Exception as e:
        return {"error": str(e)}, 500


@app.route("/offline")
def offline():
    """Offline page for PWA."""
    return render_template("offline.html")


@app.route("/newsletter/subscribe", methods=["POST"])
def newsletter_subscribe():
    """Handle newsletter subscription."""
    email = request.form.get("email", "").strip()
    
    if not email:
        return {"error": "Email is required"}, 400
    
    # Basic email validation
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return {"error": "Invalid email address"}, 400
    
    # Get user info
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')
    
    # Add to database
    result = add_subscriber(email, ip_address, user_agent)
    
    if not result["success"]:
        if result.get("error") == "already_subscribed":
            return {"error": "You're already subscribed to our newsletter!"}, 400
        return {"error": "Subscription failed. Please try again."}, 500
    
    # Send emails in background thread to avoid blocking
    token = result["token"]
    base_url = request.host_url
    
    def send_emails_async():
        send_confirmation_email(email, token, base_url)
        send_admin_notification(email)
    
    email_thread = threading.Thread(target=send_emails_async, daemon=True)
    email_thread.start()
    
    return {
        "success": True, 
        "message": "Thanks for subscribing! Please check your email to confirm your subscription."
    }


@app.route("/newsletter/confirm/<token>")
def newsletter_confirm(token):
    """Confirm newsletter subscription via email link."""
    success = confirm_subscriber(token)
    
    if success:
        message = "✓ Your subscription is confirmed! You'll now receive the latest music news."
        status = "success"
    else:
        message = "✗ Invalid or expired confirmation link. Please try subscribing again."
        status = "error"
    
    # Render a simple confirmation page
    return render_template("newsletter_confirm.html", message=message, status=status)


@app.route("/newsletter/unsubscribe")
def newsletter_unsubscribe_page():
    """Unsubscribe page."""
    email = request.args.get("email", "")
    return render_template("newsletter_unsubscribe.html", email=email)


@app.route("/newsletter/unsubscribe", methods=["POST"])
def newsletter_unsubscribe():
    """Handle newsletter unsubscription."""
    email = request.form.get("email", "").strip()
    
    if not email:
        return {"error": "Email is required"}, 400
    
    success = unsubscribe(email)
    
    if success:
        return {"success": True, "message": "You've been unsubscribed. Sorry to see you go!"}
    else:
        return {"error": "Email not found in our system"}, 404


@app.route("/newsletter/stats")
def newsletter_stats():
    """Admin endpoint to view subscriber statistics."""
    stats = get_subscriber_count()
    return {
        "confirmed_subscribers": stats["confirmed"],
        "pending_confirmations": stats["pending"],
        "total": stats["total"]
    }


@app.route("/sms/subscribe", methods=["POST"])
def sms_subscribe():
    """Handle SMS subscription."""
    phone_number = request.form.get("phone", "").strip()
    
    if not phone_number:
        return {"error": "Phone number is required"}, 400
    
    # Basic phone validation (US format)
    phone_clean = re.sub(r'[^\d+]', '', phone_number)
    if not phone_clean.startswith('+'):
        phone_clean = '+1' + phone_clean  # Assume US if no country code
    
    if len(phone_clean) < 11:
        return {"error": "Invalid phone number"}, 400
    
    # Get user info
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')
    
    # Add to database
    result = add_sms_subscriber(phone_clean, ip_address, user_agent)
    
    if not result["success"]:
        if result.get("error") == "already_subscribed":
            return {"error": "This number is already subscribed!"}, 400
        return {"error": "Subscription failed. Please try again."}, 500
    
    # Send confirmation SMS
    token = result["token"]
    sms_sent = send_sms_confirmation(phone_clean, token)
    
    # Notify admin
    send_admin_sms_notification(phone_clean)
    
    if sms_sent:
        return {
            "success": True,
            "message": "Thanks! Check your phone for a confirmation link."
        }
    else:
        return {
            "success": True,
            "message": "Subscription pending. Check your phone for confirmation."
        }


@app.route("/sms/confirm/<token>")
def sms_confirm(token):
    """Confirm SMS subscription via link."""
    success = confirm_sms_subscriber(token)
    
    if success:
        message = "✓ Your SMS subscription is confirmed! You'll get alerts for new articles."
        status = "success"
    else:
        message = "✗ Invalid or expired confirmation link. Please try subscribing again."
        status = "error"
    
    return render_template("sms_confirm.html", message=message, status=status)


@app.route("/sms/unsubscribe", methods=["GET", "POST"])
def sms_unsubscribe_route():
    """Handle SMS unsubscribe."""
    if request.method == "GET":
        return render_template("sms_unsubscribe.html")
    
    phone_number = request.form.get("phone", "").strip()
    
    if not phone_number:
        return {"error": "Phone number is required"}, 400
    
    # Clean phone number
    phone_clean = re.sub(r'[^\d+]', '', phone_number)
    if not phone_clean.startswith('+'):
        phone_clean = '+1' + phone_clean
    
    success = unsubscribe_sms(phone_clean)
    
    if success:
        return {"success": True, "message": "You've been unsubscribed from SMS alerts."}
    else:
        return {"error": "Phone number not found in our system."}, 404


@app.route("/sms/stats")
def sms_stats():
    """Admin endpoint to view SMS subscriber statistics."""
    stats = get_sms_subscriber_count()
    return {
        "confirmed_subscribers": stats["confirmed_subscribers"],
        "pending_confirmations": stats["pending_confirmations"],
        "total": stats["total"]
    }


@app.route("/admin/subscribers")
def admin_subscribers():
    """Admin page to view all subscribers - password protected."""
    import sqlite3
    from flask import request, Response
    
    # Check for basic auth
    auth = request.authorization
    admin_password = os.getenv('ADMIN_PASSWORD', 'musichub2025')
    
    if not auth or auth.password != admin_password:
        return Response(
            'Admin access required. Please enter the admin password.',
            401,
            {'WWW-Authenticate': 'Basic realm="Admin Login"'}
        )
    
    # Get email subscribers
    email_stats = get_subscriber_count()
    conn = sqlite3.connect('newsletter_subscribers.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT email, confirmed, subscribed_at, confirmed_at, ip_address
        FROM subscribers
        ORDER BY subscribed_at DESC
    """)
    email_subs = cursor.fetchall()
    conn.close()
    
    # Get SMS subscribers
    sms_stats = get_sms_subscriber_count()
    conn = sqlite3.connect('sms_subscribers.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT phone_number, confirmed, subscribed_at, confirmed_at, ip_address
        FROM sms_subscribers
        ORDER BY subscribed_at DESC
    """)
    sms_subs = cursor.fetchall()
    conn.close()
    
    return render_template('admin_subscribers.html',
                         email_stats=email_stats,
                         email_subs=email_subs,
                         sms_stats=sms_stats,
                         sms_subs=sms_subs)


@app.route("/admin/clear-pending", methods=["POST"])
def clear_pending_subscribers():
    """Admin endpoint to clear all pending subscribers - password protected."""
    from flask import request, Response
    
    # Check for basic auth
    auth = request.authorization
    admin_password = os.getenv('ADMIN_PASSWORD', 'musichub2025')
    
    if not auth or auth.password != admin_password:
        return Response(
            'Admin access required.',
            401,
            {'WWW-Authenticate': 'Basic realm="Admin Login"'}
        )
    
    # Clear pending email subscribers
    conn = sqlite3.connect('newsletter_subscribers.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subscribers WHERE confirmed = FALSE")
    email_deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    # Clear pending SMS subscribers
    conn = sqlite3.connect('sms_subscribers.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sms_subscribers WHERE confirmed = FALSE")
    sms_deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "email_deleted": email_deleted,
        "sms_deleted": sms_deleted,
        "message": f"Cleared {email_deleted} pending email and {sms_deleted} pending SMS subscribers"
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)


@app.route("/sitemap.xml")
def sitemap():
    """Generate dynamic sitemap.xml with all pages."""
    from flask import make_response
    
    # Get your actual domain
    domain = request.host_url.rstrip("/")
    
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
  <url>
    <loc>{domain}/</loc>
    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>
    <changefreq>hourly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>{domain}/releases</loc>
    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>{domain}/touring</loc>
    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>{domain}/videos</loc>
    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>{domain}/merch</loc>
    <lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
</urlset>"""
    
    response = make_response(xml)
    response.headers["Content-Type"] = "application/xml"
    return response


@app.route("/sms/status", methods=["POST"])
def sms_status_callback():
    """Handle Twilio SMS status callbacks (delivery confirmations)."""
    # This endpoint receives delivery status updates from Twilio
    # Log it but don't do anything else
    message_sid = request.form.get('MessageSid')
    message_status = request.form.get('MessageStatus')
    
    print(f"SMS Status Update - SID: {message_sid}, Status: {message_status}")
    
    return '', 200


@app.route("/robots.txt")
def robots():
    """Generate robots.txt file with comprehensive rules."""
    from flask import make_response
    
    # Get your actual domain
    domain = request.host_url.rstrip("/")
    
    txt = f"""# Music Hub - Robots.txt
User-agent: *
Allow: /
Allow: /static/*.css
Allow: /static/*.js
Allow: /static/*.png
Disallow: /admin/
Disallow: /newsletter/unsubscribe
Disallow: /sms/unsubscribe

# Crawl-delay for politeness
Crawl-delay: 1

# Sitemaps
Sitemap: {domain}/sitemap.xml

# AI Crawlers (OpenAI GPT, Google Bard, Anthropic Claude, etc.)
User-agent: GPTBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: anthropic-ai
Allow: /

User-agent: Claude-Web
Allow: /

User-agent: CCBot
Allow: /

# Search Engine Bots
User-agent: Googlebot
Allow: /
Crawl-delay: 0

User-agent: Bingbot
Allow: /
Crawl-delay: 1

User-agent: Slurp
Allow: /
"""
    
    response = make_response(txt)
    response.headers["Content-Type"] = "text/plain"
    return response


@app.route("/rss")
@app.route("/feed")
def rss_feed():
    """Generate RSS feed for latest music news."""
    from flask import make_response
    from html import escape
    
    try:
        articles = fetch_music_news(page_size=20)
    except Exception:
        articles = []
    
    domain = request.host_url.rstrip("/")
    build_date = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
    
    items = []
    for article in articles[:20]:
        pub_date = article.get("published_at_human", build_date)
        if article.get("published_at"):
            try:
                dt = datetime.fromisoformat(str(article["published_at"]).replace("Z", "+00:00"))
                pub_date = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
            except Exception:
                pass
        
        description = escape(article.get("description", ""))[:500]
        title = escape(article.get("title", ""))
        link = f"{domain}/article?url={quote_plus(article.get('url', ''))}"
        image = article.get("image", "")
        
        item = f"""
    <item>
      <title>{title}</title>
      <link>{link}</link>
      <guid isPermaLink="false">{article.get('url', '')}</guid>
      <description>{description}</description>
      <pubDate>{pub_date}</pubDate>
      <source url="{domain}">Music Hub</source>"""
        
        if image:
            item += f"""
      <enclosure url="{escape(image)}" type="image/jpeg"/>"""
        
        if article.get("genres"):
            for genre in article["genres"][:3]:
                item += f"""
      <category>{escape(genre)}</category>"""
        
        item += "\n    </item>"
        items.append(item)
    
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>Music Hub - Latest Music News</title>
    <link>{domain}/</link>
    <description>Stay updated with the latest music news, album releases, tour dates, and artist updates for rock, metal, punk, and alternative music.</description>
    <language>en-us</language>
    <copyright>Music Hub {datetime.now().year}</copyright>
    <lastBuildDate>{build_date}</lastBuildDate>
    <atom:link href="{domain}/rss" rel="self" type="application/rss+xml"/>
    <image>
      <url>{domain}/static/icon-192.png</url>
      <title>Music Hub</title>
      <link>{domain}/</link>
    </image>
{''.join(items)}
  </channel>
</rss>"""
    
    response = make_response(rss)
    response.headers["Content-Type"] = "application/rss+xml"
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

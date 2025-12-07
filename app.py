import re
import time
import os
import sqlite3
from html import unescape
from datetime import datetime
from typing import List, Dict, Any
from urllib.parse import quote_plus
from flask import Flask, render_template, request, make_response, jsonify
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

# Ticketmaster API Key
TICKETMASTER_API_KEY = os.getenv('TICKETMASTER_API_KEY', 'NdaI5iX0vU7ypgYGYkSEo3OJAM4rpfoj')

# YouTube Data API Key
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', '')

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


def get_trending_music_videos(max_results=24, region_code='US'):
    """
    Get trending music videos from YouTube.
    
    Args:
        max_results: Number of videos to return (default 24)
        region_code: Region code for localized results (default 'US')
    
    Returns:
        List of video dictionaries with id, title, channel, thumbnail, views, duration
    """
    if not YOUTUBE_API_KEY:
        return []
    
    try:
        # YouTube Data API v3 - Most Popular videos in Music category
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            'part': 'snippet,statistics,contentDetails',
            'chart': 'mostPopular',
            'videoCategoryId': '10',  # Music category
            'regionCode': region_code,
            'maxResults': max_results,
            'key': YOUTUBE_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        videos = []
        for item in data.get('items', []):
            video_id = item['id']
            snippet = item['snippet']
            statistics = item.get('statistics', {})
            content_details = item.get('contentDetails', {})
            
            videos.append({
                'id': video_id,
                'title': snippet.get('title', ''),
                'channel': snippet.get('channelTitle', ''),
                'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                'published_at': snippet.get('publishedAt', ''),
                'views': statistics.get('viewCount', '0'),
                'duration': content_details.get('duration', 'PT0S'),
                'embed_url': f"https://www.youtube.com/embed/{video_id}"
            })
        
        return videos
        
    except Exception as e:
        print(f"Error fetching trending videos: {e}")
        return []


def search_music_videos(query, max_results=24):
    """
    Search for music videos on YouTube.
    
    Args:
        query: Search query (artist name, song title, etc.)
        max_results: Number of videos to return (default 24)
    
    Returns:
        List of video dictionaries with id, title, channel, thumbnail, views, duration
    """
    if not YOUTUBE_API_KEY:
        return []
    
    try:
        # YouTube Data API v3 - Search endpoint
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            'part': 'snippet',
            'q': f"{query} music video",
            'type': 'video',
            'videoCategoryId': '10',  # Music category
            'maxResults': max_results,
            'order': 'relevance',
            'key': YOUTUBE_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Get video IDs to fetch statistics
        video_ids = [item['id']['videoId'] for item in data.get('items', [])]
        
        if not video_ids:
            return []
        
        # Fetch video details (statistics and duration)
        details_url = "https://www.googleapis.com/youtube/v3/videos"
        details_params = {
            'part': 'statistics,contentDetails',
            'id': ','.join(video_ids),
            'key': YOUTUBE_API_KEY
        }
        
        details_response = requests.get(details_url, params=details_params, timeout=10)
        details_response.raise_for_status()
        details_data = details_response.json()
        
        # Map details by video ID
        details_map = {item['id']: item for item in details_data.get('items', [])}
        
        videos = []
        for item in data.get('items', []):
            video_id = item['id']['videoId']
            snippet = item['snippet']
            details = details_map.get(video_id, {})
            statistics = details.get('statistics', {})
            content_details = details.get('contentDetails', {})
            
            videos.append({
                'id': video_id,
                'title': snippet.get('title', ''),
                'channel': snippet.get('channelTitle', ''),
                'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                'published_at': snippet.get('publishedAt', ''),
                'views': statistics.get('viewCount', '0'),
                'duration': content_details.get('duration', 'PT0S'),
                'embed_url': f"https://www.youtube.com/embed/{video_id}"
            })
        
        return videos
        
    except Exception as e:
        print(f"Error searching videos: {e}")
        return []


# Jinja2 template filters for video page formatting
@app.template_filter('format_views')
def format_views(views):
    """Format view count with K/M/B suffixes."""
    try:
        views = int(views)
        if views >= 1_000_000_000:
            return f"{views / 1_000_000_000:.1f}B"
        elif views >= 1_000_000:
            return f"{views / 1_000_000:.1f}M"
        elif views >= 1_000:
            return f"{views / 1_000:.1f}K"
        else:
            return str(views)
    except (ValueError, TypeError):
        return "0"


@app.template_filter('format_date')
def format_date(date_str):
    """Format ISO date string to human-readable format."""
    try:
        from datetime import datetime
        date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        now = datetime.now(date.tzinfo)
        delta = now - date
        
        if delta.days == 0:
            return "Today"
        elif delta.days == 1:
            return "Yesterday"
        elif delta.days < 7:
            return f"{delta.days} days ago"
        elif delta.days < 30:
            weeks = delta.days // 7
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
        elif delta.days < 365:
            months = delta.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        else:
            years = delta.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
    except Exception:
        return date_str



def get_spotify_search_url(artist: str, track: str = "") -> str:
    """Generate Spotify search URL."""
    query = f"{artist} {track}".strip()
    return f"https://open.spotify.com/search/{quote_plus(query)}"


def get_apple_music_search_url(artist: str, track: str = "") -> str:
    """Generate Apple Music search URL."""
    from urllib.parse import quote
    query = f"{artist} {track}".strip()
    return f"https://music.apple.com/us/search?term={quote(query)}"


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


def filter_by_price(events, price_min=None, price_max=None):
    """Filter events by price range."""
    if not events or (price_min is None and price_max is None):
        return events
    
    filtered = []
    for event in events:
        # Skip events without price info
        if 'price_range' not in event or not event['price_range']:
            continue
        
        price_str = event['price_range']
        # Parse price range like "$45 - $125"
        try:
            if '-' in price_str:
                parts = price_str.replace('$', '').split('-')
                min_price = float(parts[0].strip())
                max_price = float(parts[1].strip())
            else:
                # Single price
                min_price = max_price = float(price_str.replace('$', '').strip())
            
            # Check if price range overlaps with filter
            if price_min is not None and max_price < price_min:
                continue
            if price_max is not None and min_price > price_max:
                continue
            
            filtered.append(event)
        except (ValueError, IndexError):
            # Skip events with unparseable price
            continue
    
    return filtered


def get_artist_tour_dates(artist_name: str, limit: int = 50, latlong: str = None, radius: int = 50, sort: str = "date,asc", genre_id: str = None, start_date: str = None, end_date: str = None, price_min: int = None, price_max: int = None):
    """
    Fetch upcoming tour dates from Ticketmaster Discovery API.
    Returns list of tour date dicts.
    """
    # Ticketmaster Discovery API endpoint
    base_url = "https://app.ticketmaster.com/discovery/v2/events.json"
    
    params = {
        "apikey": TICKETMASTER_API_KEY,
        "classificationName": "Music",
        "size": min(limit, 200),
        "sort": sort
    }
    
    # Add keyword if provided
    if artist_name and artist_name.lower() != 'concert':
        params["keyword"] = artist_name
    
    # Add location if provided (format: "latitude,longitude")
    if latlong:
        params["latlong"] = latlong
        params["radius"] = radius
        params["unit"] = "miles"
    
    # Add genre filter
    if genre_id:
        params["genreId"] = genre_id
    
    # Add date range filter
    if start_date:
        params["startDateTime"] = start_date
    if end_date:
        params["endDateTime"] = end_date
    
    # Note: Ticketmaster doesn't support price filtering in API, we'll filter results after
    
    headers = {
        "User-Agent": USER_AGENT
    }
    
    try:
        resp = requests.get(base_url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        # Extract events from response
        embedded = data.get('_embedded', {})
        events = embedded.get('events', [])
        
        if not events:
            return []
        
        # Process and return events (remove duplicates)
        tour_dates = []
        seen_event_ids = set()
        
        for event in events:
            event_id = event.get('id', '')
            
            # Skip duplicate events
            if event_id in seen_event_ids:
                continue
            seen_event_ids.add(event_id)
            
            # Get event details
            event_name = event.get('name', '')
            event_url = event.get('url', '')
            
            # Get date/time
            dates = event.get('dates', {})
            start = dates.get('start', {})
            date_str = start.get('localDate', '')
            time_str = start.get('localTime', '')
            datetime_str = f"{date_str}T{time_str}" if date_str and time_str else date_str
            
            # Get venue info
            embedded_venue = event.get('_embedded', {})
            venues = embedded_venue.get('venues', [])
            
            venue_name = 'Venue TBA'
            city = ''
            region = ''
            country = ''
            
            if venues:
                venue = venues[0]
                venue_name = venue.get('name', 'Venue TBA')
                city_obj = venue.get('city', {})
                city = city_obj.get('name', '') if isinstance(city_obj, dict) else ''
                state_obj = venue.get('state', {})
                region = state_obj.get('stateCode', '') if isinstance(state_obj, dict) else ''
                country_obj = venue.get('country', {})
                country = country_obj.get('countryCode', '') if isinstance(country_obj, dict) else ''
            
            # Get ticket status
            sales = event.get('sales', {})
            public_sales = sales.get('public', {})
            ticket_status = 'Available'
            if public_sales.get('startDateTime'):
                ticket_status = 'On Sale'
            
            # Get image
            images = event.get('images', [])
            artist_image = ''
            if images:
                # Get the best quality image
                for img in images:
                    if img.get('ratio') == '16_9' and img.get('width', 0) > 1000:
                        artist_image = img.get('url', '')
                        break
                if not artist_image and images:
                    artist_image = images[0].get('url', '')
            
            # Get price range
            price_ranges = event.get('priceRanges', [])
            price_info = ''
            if price_ranges:
                min_price = price_ranges[0].get('min', '')
                max_price = price_ranges[0].get('max', '')
                currency = price_ranges[0].get('currency', 'USD')
                if min_price and max_price:
                    price_info = f"${min_price}-${max_price}"
            
            tour_date = {
                'id': event.get('id', ''),
                'artist': artist_name,
                'event_name': event_name,
                'datetime': datetime_str,
                'venue_name': venue_name,
                'city': city,
                'region': region,
                'country': country,
                'ticket_url': event_url,
                'ticket_status': ticket_status,
                'description': '',
                'lineup': [],
                'artist_image': artist_image,
                'price_info': price_info,
            }
            
            tour_dates.append(tour_date)
        
        return tour_dates
        
    except requests.HTTPError as e:
        if e.response.status_code == 429:
            print(f"Ticketmaster rate limit exceeded. Using fallback empty results.")
            # Rate limit hit - return empty gracefully
            return []
        print(f"Ticketmaster API HTTP error for {artist_name}: {e}")
        return []
    except Exception as e:
        print(f"Ticketmaster API error for {artist_name}: {e}")
        return []


def search_releases_by_artist(artist_name: str, year: int = None, limit: int = 100, offset: int = 0, max_retries: int = 3):
    """
    Call MusicBrainz search by artist name:
      /ws/2/release/?query=artist:ARTIST&fmt=json&limit=...
    Optionally filter by year if provided.
    Supports pagination with offset parameter.
    Returns list of releases (dicts).
    """
    # Use quotes for exact phrase matching in MusicBrainz
    # Filter for albums only (type:album) to exclude singles, EPs, etc.
    query = f'artist:"{artist_name}" AND type:album AND (status:official OR status:promotion)'
    if year:
        query += f" AND date:{year}*"
    
    params = {
        "query": query,
        "fmt": "json",
        "limit": str(limit),
        "offset": str(offset),
    }
    headers = {
        "User-Agent": USER_AGENT,
    }

    # Retry logic for connection issues
    for attempt in range(max_retries):
        try:
            resp = requests.get(API_BASE, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data.get("releases", [])
        except (requests.ConnectionError, ConnectionResetError) as e:
            if attempt < max_retries - 1:
                # Wait before retrying (exponential backoff)
                time.sleep(2 ** attempt)
                continue
            else:
                # Last attempt failed, re-raise
                raise
        except requests.HTTPError as e:
            # Don't retry on HTTP errors (404, 500, etc.)
            raise


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
    artist_filter = ""
    
    # Don't auto-load results on first visit - wait for user to submit
    should_fetch = False

    if request.method == "POST":
        # Get form values
        date_value = request.form.get("date", "").strip()
        start_str = request.form.get("start_year", "").strip()
        end_str = request.form.get("end_year", "").strip()
        artist_filter = request.form.get("artist_filter", "").strip()

        # If artist is provided, ignore the date completely
        if artist_filter:
            # Clear date-related variables when searching by artist
            mm_dd = None
            pretty_date = ""
        else:
            # Date is required when not searching by artist
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
    if should_fetch and not error:
        # If artist filter is provided, search by artist instead of date
        if artist_filter:
            results = []
            seen_titles = set()  # Track unique album titles to avoid duplicates
            
            # Search by artist - get maximum results from MusicBrainz
            try:
                # MusicBrainz max limit is 100 per request, so we need to paginate
                all_releases = []
                offset = 0
                limit = 100
                max_results = 2000  # Get up to 2000 results total to ensure we get recent releases
                
                while offset < max_results:
                    # Fetch releases with pagination
                    releases = search_releases_by_artist(artist_filter, year=None, limit=limit, offset=offset)
                    
                    if not releases:
                        break  # No more results
                    
                    all_releases.extend(releases)
                    offset += limit
                    
                    # Stop if we got fewer results than requested (last page)
                    if len(releases) < limit:
                        break
                    
                    # Be polite to MusicBrainz API
                    time.sleep(1)
                
                # Process all releases and remove duplicates
                for r in all_releases:
                    title = r.get("title")
                    date = r.get("date")
                    
                    # Skip if no title
                    if not title:
                        continue
                    
                    # Extract year from release date
                    release_year = None
                    if date:
                        try:
                            if len(date) >= 4:
                                release_year = int(date[:4])
                        except (ValueError, TypeError):
                            pass
                    
                    # Skip if no year could be extracted
                    if not release_year:
                        continue
                    
                    # Create a unique key for deduplication (title + year)
                    # This helps avoid showing multiple editions of the same album
                    unique_key = f"{title.lower().strip()}_{release_year}"
                    
                    if unique_key in seen_titles:
                        continue  # Skip duplicate
                    
                    seen_titles.add(unique_key)
                    
                    artist = None
                    ac = r.get("artist-credit") or []
                    if ac and isinstance(ac, list) and "name" in ac[0]:
                        artist = ac[0]["name"]
                    
                    mbid = r.get("id")
                    url = f"/release/{mbid}" if mbid else None
                    
                    # Try to get cover art from Cover Art Archive
                    cover_art = None
                    if mbid:
                        cover_art = f"https://coverartarchive.org/release/{mbid}/front-250"

                    results.append(
                        type("Release", (object,), {
                            "year": release_year,
                            "title": title,
                            "artist": artist,
                            "date": date,
                            "url": url,
                            "cover_art": cover_art,
                        })
                    )
                
            except (requests.HTTPError, requests.ConnectionError, ConnectionResetError) as e:
                error = "Unable to connect to MusicBrainz. The music database may be experiencing high traffic. Please try again in a moment."
                print(f"MusicBrainz connection error: {e}")
            except Exception as e:
                error = "An error occurred while searching for the artist. Please try again."
                print(f"Artist search error: {e}")
        
        # Search by date if provided and no artist filter
        elif mm_dd:
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
                    url = f"/release/{mbid}" if mbid else None
                    
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

            # Save to cache for future requests (only for date searches, not artist searches)
            if mm_dd:
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
        artist_filter=artist_filter,
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
        # Use simple string replacement for consistency with template behavior
        search_query = f"{artist_name} {title}".replace(" ", "%20")
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


@app.route("/api/artist-events")
def api_artist_events():
    """API endpoint to fetch events for a specific artist."""
    artist = request.args.get('artist', '').strip()
    
    if not artist:
        return jsonify({'error': 'Artist name required'}), 400
    
    try:
        # Fetch events for this artist (no location filter for followed artists)
        events = get_artist_tour_dates(
            artist_name=artist,
            limit=10,
            latlong=None,
            radius=None,
            sort='date,asc'
        )
        
        return jsonify({'events': events})
    except Exception as e:
        print(f"Error fetching artist events: {str(e)}")
        return jsonify({'error': 'Failed to fetch events'}), 500


@app.route("/api/recommended-events")
def api_recommended_events():
    """API endpoint to fetch recommended events."""
    limit = request.args.get('limit', '20')
    latlong = request.args.get('latlong', '').strip()
    radius = request.args.get('radius', '50').strip()
    
    try:
        # Fetch trending/popular events
        events = get_artist_tour_dates(
            artist_name='',  # Empty to get general events
            limit=int(limit),
            latlong=latlong if latlong else None,
            radius=radius if latlong else None,
            sort='relevance,desc'
        )
        
        return jsonify({'events': events})
    except Exception as e:
        print(f"Error fetching recommended events: {str(e)}")
        return jsonify({'error': 'Failed to fetch recommendations'}), 500


@app.route("/touring")
def touring():
    """Touring page with concert tour data from Ticketmaster API."""
    artist_query = request.args.get('artist', '').strip()
    location_query = request.args.get('location', '').strip()
    latlong = request.args.get('latlong', '').strip()
    radius = request.args.get('radius', '50')
    view_mode = request.args.get('view', 'local')  # 'local' or 'nationwide' or market code
    
    # Filter parameters
    genre_filter = request.args.get('genre', '').strip()
    date_filter = request.args.get('date_range', '').strip()
    price_filter = request.args.get('price', '').strip()
    
    # Advanced search parameters
    multi_artist = request.args.get('multi_artist', '').strip()
    venue_query = request.args.get('venue', '').strip()
    festival_only = request.args.get('festival_only', '').strip() == 'true'
    
    tours = []
    trending_now = []
    coming_soon = []
    last_chance = []
    nearby_events = []
    az_guide = []
    random_discovery = []
    popular_venues = []
    error = None
    
    try:
        # Convert radius to int
        try:
            radius = int(radius)
        except:
            radius = 50
        
        # Handle location query (city name or ZIP code)
        if location_query and not latlong:
            # Use Nominatim API to geocode location
            geocode_url = "https://nominatim.openstreetmap.org/search"
            geocode_params = {
                'q': location_query,
                'format': 'json',
                'limit': 1,
                'countrycodes': 'us,ca'  # Limit to US and Canada
            }
            geocode_headers = {'User-Agent': USER_AGENT}
            
            try:
                geo_resp = requests.get(geocode_url, params=geocode_params, headers=geocode_headers, timeout=5)
                geo_resp.raise_for_status()
                geo_data = geo_resp.json()
                
                if geo_data and len(geo_data) > 0:
                    lat = geo_data[0]['lat']
                    lon = geo_data[0]['lon']
                    latlong = f"{lat},{lon}"
            except Exception as geo_error:
                print(f"Geocoding error: {geo_error}")
        
        # Handle nationwide view (no location filter)
        if view_mode == 'nationwide':
            latlong = ''
            radius = 500  # Large radius for nationwide
        
        # Process filters
        genre_id = None
        start_date = None
        end_date = None
        price_min = None
        price_max = None
        
        # Genre filter mapping (Ticketmaster Genre IDs)
        genre_map = {
            'rock': 'KnvZfZ7vAeA',
            'pop': 'KnvZfZ7vAev',
            'country': 'KnvZfZ7vAv6',
            'hiphop': 'KnvZfZ7vAv1',
            'rap': 'KnvZfZ7vAv1',
            'rb': 'KnvZfZ7vAee',
            'jazz': 'KnvZfZ7vAvE',
            'metal': 'KnvZfZ7vAvt',
            'alternative': 'KnvZfZ7vAvv',
            'edm': 'KnvZfZ7vAvF',
            'electronic': 'KnvZfZ7vAvF',
            'blues': 'KnvZfZ7vAvd'
        }
        
        if genre_filter and genre_filter.lower() in genre_map:
            genre_id = genre_map[genre_filter.lower()]
        
        # Date range filter
        from datetime import datetime, timedelta
        today = datetime.now()
        
        if date_filter == 'today':
            start_date = today.strftime('%Y-%m-%dT00:00:00Z')
            end_date = today.strftime('%Y-%m-%dT23:59:59Z')
        elif date_filter == 'tomorrow':
            tomorrow = today + timedelta(days=1)
            start_date = tomorrow.strftime('%Y-%m-%dT00:00:00Z')
            end_date = tomorrow.strftime('%Y-%m-%dT23:59:59Z')
        elif date_filter == 'this_week':
            start_date = today.strftime('%Y-%m-%dT00:00:00Z')
            end_week = today + timedelta(days=7)
            end_date = end_week.strftime('%Y-%m-%dT23:59:59Z')
        elif date_filter == 'this_weekend':
            # Find next Friday, Saturday, Sunday
            days_until_friday = (4 - today.weekday()) % 7
            if days_until_friday == 0 and today.hour >= 18:
                days_until_friday = 7
            friday = today + timedelta(days=days_until_friday)
            sunday = friday + timedelta(days=2)
            start_date = friday.strftime('%Y-%m-%dT00:00:00Z')
            end_date = sunday.strftime('%Y-%m-%dT23:59:59Z')
        elif date_filter == 'next_30':
            start_date = today.strftime('%Y-%m-%dT00:00:00Z')
            end_30 = today + timedelta(days=30)
            end_date = end_30.strftime('%Y-%m-%dT23:59:59Z')
        
        # Price filter
        if price_filter:
            if price_filter == 'free':
                price_min = 0
                price_max = 0
            elif price_filter == 'under_50':
                price_min = 0
                price_max = 50
            elif price_filter == '50_100':
                price_min = 50
                price_max = 100
            elif price_filter == '100_200':
                price_min = 100
                price_max = 200
            elif price_filter == 'over_200':
                price_min = 200
                price_max = 10000
            
        if multi_artist:
            # Multi-artist search
            artists = [a.strip() for a in multi_artist.split('\n') if a.strip()]
            all_tours = []
            for artist in artists[:10]:  # Limit to 10 artists
                artist_tours = get_artist_tour_dates(artist, limit=20, latlong=latlong, radius=radius, genre_id=genre_id, start_date=start_date, end_date=end_date)
                all_tours.extend(artist_tours)
            
            # Remove duplicates based on event URL
            seen_urls = set()
            tours = []
            for event in all_tours:
                if event['ticket_url'] not in seen_urls:
                    seen_urls.add(event['ticket_url'])
                    tours.append(event)
            
            # Sort by date
            tours.sort(key=lambda x: x.get('datetime', '9999-12-31'))
            
            # Apply price filter
            if price_min is not None or price_max is not None:
                tours = filter_by_price(tours, price_min, price_max)
            
            if not tours:
                error = f"No upcoming events found for the selected artists"
                
        elif venue_query:
            # Venue-specific search
            # Ticketmaster API: search by venue name using keyword parameter
            try:
                url = f"https://app.ticketmaster.com/discovery/v2/events.json"
                params = {
                    'apikey': TICKETMASTER_API_KEY,
                    'keyword': venue_query,
                    'size': 50,
                    'sort': 'date,asc'
                }
                
                if latlong:
                    params['latlong'] = latlong
                    params['radius'] = radius
                
                if genre_id:
                    params['genreId'] = genre_id
                
                if start_date:
                    params['startDateTime'] = start_date
                if end_date:
                    params['endDateTime'] = end_date
                
                response = requests.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if '_embedded' in data and 'events' in data['_embedded']:
                        events = data['_embedded']['events']
                        
                        for event in events:
                            # Filter to only include events at venues matching the query
                            venue_name = event.get('_embedded', {}).get('venues', [{}])[0].get('name', '')
                            if venue_query.lower() in venue_name.lower():
                                event_info = {
                                    'event_name': event.get('name', 'Unknown Event'),
                                    'artist': event.get('_embedded', {}).get('attractions', [{}])[0].get('name', 'Various Artists') if event.get('_embedded', {}).get('attractions') else 'Various Artists',
                                    'venue_name': venue_name,
                                    'city': event.get('_embedded', {}).get('venues', [{}])[0].get('city', {}).get('name', 'Unknown'),
                                    'region': event.get('_embedded', {}).get('venues', [{}])[0].get('state', {}).get('stateCode', ''),
                                    'ticket_url': event.get('url', '#'),
                                    'datetime': event.get('dates', {}).get('start', {}).get('dateTime', ''),
                                    'artist_image': event.get('images', [{}])[0].get('url', '') if event.get('images') else '',
                                    'price_range': f"${event.get('priceRanges', [{}])[0].get('min', 'N/A')} - ${event.get('priceRanges', [{}])[0].get('max', 'N/A')}" if event.get('priceRanges') else None
                                }
                                tours.append(event_info)
                
                # Apply price filter
                if price_min is not None or price_max is not None:
                    tours = filter_by_price(tours, price_min, price_max)
                
                if not tours:
                    error = f"No upcoming events found at '{venue_query}'"
            except Exception as e:
                print(f"Error fetching venue events: {str(e)}")
                error = "Failed to fetch venue events"
                
        elif artist_query:
            # Search for specific artist
            tours = get_artist_tour_dates(artist_query, limit=50, latlong=latlong, radius=radius, genre_id=genre_id, start_date=start_date, end_date=end_date, price_min=price_min, price_max=price_max)
            
            # Filter by price if specified (post-processing since API doesn't support it)
            if price_min is not None or price_max is not None:
                tours = filter_by_price(tours, price_min, price_max)
            
            if not tours:
                error = f"No upcoming tour dates found for '{artist_query}'"
        else:
            # Fetch different categories for carousels
            
            # 1. Trending Now - relevance sorting for most popular/trending events
            trending_now = get_artist_tour_dates('concert', limit=12, latlong=latlong, radius=radius, sort="relevance,desc", genre_id=genre_id, start_date=start_date, end_date=end_date)
            
            # 2. Coming Soon - tickets going on sale soonest
            coming_soon = get_artist_tour_dates('concert', limit=12, latlong=latlong, radius=radius, sort="onSaleStartDate,asc", genre_id=genre_id, start_date=start_date, end_date=end_date)
            
            # 3. Last Chance - soonest events (happening this week/soon)
            last_chance = get_artist_tour_dates('concert', limit=12, latlong=latlong, radius=radius, sort="date,asc", genre_id=genre_id, start_date=start_date, end_date=end_date)
            
            # 4. Nearby Events - closest events geographically
            if latlong:
                nearby_events = get_artist_tour_dates('concert', limit=12, latlong=latlong, radius=radius, sort="distance,asc", genre_id=genre_id, start_date=start_date, end_date=end_date)
            else:
                nearby_events = []
            
            # 5. A-Z Artist Guide - alphabetically sorted events
            az_guide = get_artist_tour_dates('concert', limit=12, latlong=latlong, radius=radius, sort="name,asc", genre_id=genre_id, start_date=start_date, end_date=end_date)
            
            # 6. Random Discovery - random events for exploration
            random_discovery = get_artist_tour_dates('concert', limit=12, latlong=latlong, radius=radius, sort="random", genre_id=genre_id, start_date=start_date, end_date=end_date)
            
            # 7. Popular Venues - sorted by venue name, grouped by venue
            venue_events = get_artist_tour_dates('concert', limit=200, latlong=latlong, radius=radius, sort="venueName,asc", genre_id=genre_id, start_date=start_date, end_date=end_date)
            
            # Apply price filter to all carousels if specified
            if price_min is not None or price_max is not None:
                trending_now = filter_by_price(trending_now, price_min, price_max)
                coming_soon = filter_by_price(coming_soon, price_min, price_max)
                last_chance = filter_by_price(last_chance, price_min, price_max)
                nearby_events = filter_by_price(nearby_events, price_min, price_max)
                az_guide = filter_by_price(az_guide, price_min, price_max)
                random_discovery = filter_by_price(random_discovery, price_min, price_max)
                venue_events = filter_by_price(venue_events, price_min, price_max)
            if venue_events:
                # Group by venue and count events
                venue_dict = {}
                for event in venue_events:
                    venue_name = event['venue_name']
                    if venue_name != 'Venue TBA':
                        if venue_name not in venue_dict:
                            # Create venue entry with first event's image and count events
                            venue_dict[venue_name] = {
                                'venue_name': venue_name,
                                'city': event['city'],
                                'region': event['region'],
                                'artist_image': event.get('artist_image', ''),
                                'event_count': 1,
                                'venue_id': venue_name.lower().replace(' ', '-').replace("'", '').replace('.', '')
                            }
                        else:
                            venue_dict[venue_name]['event_count'] += 1
                            # Use image if current venue entry doesn't have one
                            if not venue_dict[venue_name]['artist_image'] and event.get('artist_image'):
                                venue_dict[venue_name]['artist_image'] = event['artist_image']
                popular_venues = list(venue_dict.values())[:12]
            
    except Exception as e:
        error = "Unable to fetch tour data at this time. Please try again later."
        print(f"Touring error: {e}")
    
    return render_template(
        "touring.html",
        tours=tours,
        trending_now=trending_now,
        coming_soon=coming_soon,
        last_chance=last_chance,
        nearby_events=nearby_events,
        az_guide=az_guide,
        random_discovery=random_discovery,
        popular_venues=popular_venues,
        artist_query=artist_query,
        location_query=location_query,
        view_mode=view_mode,
        genre_filter=genre_filter,
        date_filter=date_filter,
        price_filter=price_filter,
        multi_artist=multi_artist,
        venue_query=venue_query,
        festival_only=festival_only,
        error=error
    )


@app.route("/venue/<venue_id>")
def venue_detail(venue_id):
    """Show all events at a specific venue."""
    venue_name = request.args.get('name', '').strip()
    latlong = request.args.get('latlong', '').strip()
    radius = request.args.get('radius', '100')
    
    events = []
    error = None
    
    try:
        radius = int(radius)
    except:
        radius = 100
    
    try:
        # Search directly for the venue name to get all its events
        # Use the actual venue name instead of generic "concert" search
        venue_events = get_artist_tour_dates(venue_name, limit=200, latlong=latlong, radius=radius)
        
        # Filter to ensure we only show events at this exact venue
        # (in case the search returns events from similarly named venues)
        events = [event for event in venue_events if event['venue_name'].lower().replace(' ', '-').replace("'", '').replace('.', '') == venue_id.replace('.', '')]
        
        # If no events found with venue name search, try broader area search as fallback
        if not events:
            all_events = get_artist_tour_dates('concert', limit=200, latlong=latlong, radius=radius)
            events = [event for event in all_events if event['venue_name'].lower().replace(' ', '-').replace("'", '').replace('.', '') == venue_id.replace('.', '')]
        
        if not events:
            error = f"No upcoming events found at {venue_name}"
    except Exception as e:
        error = "Unable to fetch venue events at this time."
        print(f"Venue detail error: {e}")
    
    return render_template(
        "venue_detail.html",
        venue_name=venue_name,
        events=events,
        error=error
    )


@app.route("/videos")
def videos():
    """Videos page with YouTube integration."""
    # Get search query from URL
    search_query = request.args.get('search', '').strip()
    
    if search_query:
        # Search for specific artist/song
        videos = search_music_videos(search_query, max_results=24)
        page_title = f"Videos: {search_query}"
    else:
        # Show trending music videos
        videos = get_trending_music_videos(max_results=24)
        page_title = "Trending Music Videos"
    
    return render_template(
        "videos.html",
        videos=videos,
        search_query=search_query,
        page_title=page_title
    )


def get_printful_products():
    """Fetch products from Printful Store API."""
    # Demo products to show if API fails or returns nothing
    demo_products = [
        {
            "id": 1,
            "name": "Music Hub Classic T-Shirt",
            "description": "Premium cotton t-shirt with Music Hub logo",
            "price": "24.99",
            "currency": "USD",
            "image": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=500",
            "variants": ["S", "M", "L", "XL"],
        },
        {
            "id": 2,
            "name": "Music Lover Hoodie",
            "description": "Cozy hoodie for true music fans",
            "price": "44.99",
            "currency": "USD",
            "image": "https://images.unsplash.com/photo-1556821840-3a63f95609a7?w=500",
            "variants": ["S", "M", "L", "XL"],
        },
        {
            "id": 3,
            "name": "Vinyl Enthusiast Poster",
            "description": "High-quality print for your music room",
            "price": "19.99",
            "currency": "USD",
            "image": "https://images.unsplash.com/photo-1594623930572-300a3011d9ae?w=500",
            "variants": ["18x24", "24x36"],
        },
    ]
    
    # Printful Store API endpoint
    store_id = os.environ.get("PRINTFUL_STORE_ID", "")
    
    if not store_id:
        return demo_products
    
    try:
        # Printful Store API uses store ID
        api_url = f"https://api.printful.com/store/products"
        headers = {
            "Authorization": f"Bearer {os.environ.get('PRINTFUL_API_KEY', '')}",
        }
        
        response = requests.get(api_url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        # Transform Printful response to our format
        products = []
        for item in data.get("result", []):
            sync_product = item.get("sync_product", {})
            sync_variants = item.get("sync_variants", [])
            
            if sync_variants:
                variant = sync_variants[0]
                products.append({
                    "id": sync_product.get("id"),
                    "name": sync_product.get("name", ""),
                    "description": sync_product.get("description", ""),
                    "price": variant.get("retail_price", "0.00"),
                    "currency": variant.get("currency", "USD"),
                    "image": sync_product.get("thumbnail_url", ""),
                    "variants": [v.get("name", "") for v in sync_variants],
                    "url": sync_product.get("url", ""),
                })
        
        # If no products from API, return demo products
        return products if products else demo_products
    except Exception as e:
        print(f"Printful API error: {e}")
        # Return demo products on error
        return demo_products


@app.route("/merch")
def merch():
    """Merch page with Printful products."""
    try:
        # Get Printful products
        products = get_printful_products()
        return render_template("merch.html", products=products)
    except Exception as e:
        print(f"Error fetching merch: {e}")
        return render_template("merch.html", products=[], error=str(e))


@app.route("/subscribe")
def subscribe():
    """Subscribe page for newsletter and SMS signups."""
    return render_template("subscribe.html")


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
    # Accept both JSON and form data
    if request.is_json:
        email = request.json.get("email", "").strip()
    else:
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
    # Accept both JSON and form data
    if request.is_json:
        phone_number = request.json.get("phone", "").strip()
    else:
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

#!/usr/bin/env python3
"""
Background task to monitor for new articles and send SMS notifications.
Run this separately: python send_article_notifications.py
"""
import time
import sys
import os
import feedparser
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
from urllib.parse import quote_plus
from sms_db import get_all_confirmed_sms_subscribers, article_already_sent, mark_article_sent

try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    print("Warning: Twilio not installed. Run: pip install twilio")
    sys.exit(1)

# Configuration
import os
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', 'your-account-sid')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', 'your-auth-token')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '+1234567890')
SITE_URL = os.getenv('SITE_URL', 'http://localhost:5001')
LOUDWIRE_FEED = "https://loudwire.com/category/news/feed"
CHECK_INTERVAL = 300  # Check every 5 minutes

def fetch_latest_articles(limit=5):
    """Fetch the latest articles from RSS feed."""
    try:
        feed = feedparser.parse(LOUDWIRE_FEED)
        articles = []
        
        for entry in feed.entries[:limit]:
            articles.append({
                'title': entry.get('title', 'Untitled'),
                'url': entry.get('link', ''),
                'published': entry.get('published', '')
            })
        
        return articles
    except Exception as e:
        print(f"Error fetching articles: {e}")
        return []

def send_sms_notification(article_title, article_url):
    """Send SMS notification to all subscribers."""
    if TWILIO_ACCOUNT_SID == "your-account-sid":
        print(f"Twilio not configured. Would send notification for: {article_title}")
        return 0
    
    # Check if already sent
    if article_already_sent(article_url):
        return 0
    
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        subscribers = get_all_confirmed_sms_subscribers()
        
        if not subscribers:
            print("No SMS subscribers")
            return 0
        
        # Truncate title
        short_title = article_title[:100] + "..." if len(article_title) > 100 else article_title
        full_url = f"{SITE_URL}/article?url={quote_plus(article_url)}"
        
        message_body = f"🎵 New on Music Hub:\n\n{short_title}\n\nRead more: {full_url}\n\nReply STOP to unsubscribe"
        
        sent_count = 0
        for _, phone_number, _, _ in subscribers:
            try:
                message = client.messages.create(
                    body=message_body,
                    from_=TWILIO_PHONE_NUMBER,
                    to=phone_number
                )
                print(f"✓ SMS sent to {phone_number}: {message.sid}")
                sent_count += 1
                time.sleep(1)  # Rate limiting
            except Exception as e:
                print(f"✗ Error sending to {phone_number}: {e}")
        
        # Mark as sent
        if sent_count > 0:
            mark_article_sent(article_url, sent_count)
            print(f"✓ Marked article as sent ({sent_count} recipients)")
        
        return sent_count
        
    except Exception as e:
        print(f"Error in send_sms_notification: {e}")
        return 0

def monitor_new_articles():
    """Monitor for new articles and send notifications."""
    print("Starting article monitoring...")
    print(f"Checking every {CHECK_INTERVAL} seconds")
    print(f"Site URL: {SITE_URL}")
    print("Press Ctrl+C to stop\n")
    
    last_check = {}
    
    while True:
        try:
            articles = fetch_latest_articles(limit=3)
            
            for article in articles:
                url = article['url']
                title = article['title']
                
                # Check if this is a new article
                if url not in last_check and not article_already_sent(url):
                    print(f"\n📰 New article detected: {title}")
                    sent_count = send_sms_notification(title, url)
                    
                    if sent_count > 0:
                        print(f"✓ Notification sent to {sent_count} subscribers")
                    else:
                        print("⏭ Skipped (no subscribers or already sent)")
                
                last_check[url] = True
            
            # Keep only recent 50 articles in memory
            if len(last_check) > 50:
                # Remove oldest entries
                items = list(last_check.items())
                last_check = dict(items[-50:])
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Checked feed. {len(articles)} articles. Next check in {CHECK_INTERVAL}s")
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n\nStopping article monitoring...")
            break
        except Exception as e:
            print(f"Error in monitoring loop: {e}")
            time.sleep(60)  # Wait a minute before retrying

if __name__ == "__main__":
    if not TWILIO_AVAILABLE:
        print("Please install Twilio: pip install twilio")
        sys.exit(1)
    
    monitor_new_articles()

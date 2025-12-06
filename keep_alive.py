#!/usr/bin/env python3
"""
Keep-alive script to prevent Render free tier from spinning down.
Pings the site every 10 minutes to keep it active.
"""

import time
import requests
from datetime import datetime

# Your Render site URL
SITE_URL = "https://music-news-site.onrender.com"

def ping_site():
    """Send a ping request to keep the site alive."""
    try:
        response = requests.get(SITE_URL, timeout=30)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if response.status_code == 200:
            print(f"[{timestamp}] ✓ Successfully pinged {SITE_URL} - Status: {response.status_code}")
        else:
            print(f"[{timestamp}] ⚠ Pinged {SITE_URL} - Status: {response.status_code}")
    except requests.RequestException as e:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] ✗ Error ping {SITE_URL}: {e}")

if __name__ == "__main__":
    print(f"Starting keep-alive service for {SITE_URL}")
    print("Pinging every 10 minutes...")
    print("-" * 60)
    
    while True:
        ping_site()
        # Sleep for 10 minutes (600 seconds)
        time.sleep(600)

#!/usr/bin/env python3
"""
View all newsletter subscribers
"""
from newsletter_db import get_all_confirmed_subscribers, get_subscriber_count
import sqlite3
from datetime import datetime

def view_all_subscribers():
    """Display all subscribers (confirmed and pending)"""
    conn = sqlite3.connect('newsletter_subscribers.db')
    cursor = conn.cursor()
    
    # Get all subscribers
    cursor.execute("""
        SELECT email, confirmed, subscribed_at, confirmed_at, ip_address
        FROM subscribers
        ORDER BY subscribed_at DESC
    """)
    
    all_subscribers = cursor.fetchall()
    conn.close()
    
    if not all_subscribers:
        print("\n📭 No subscribers yet.\n")
        return
    
    # Get counts
    stats = get_subscriber_count()
    
    print("\n" + "="*80)
    print("📧 NEWSLETTER SUBSCRIBERS")
    print("="*80)
    print(f"✅ Confirmed: {stats['confirmed_subscribers']}")
    print(f"⏳ Pending:   {stats['pending_confirmations']}")
    print(f"📊 Total:     {stats['total']}")
    print("="*80 + "\n")
    
    # Display confirmed subscribers
    confirmed = [s for s in all_subscribers if s[1]]
    if confirmed:
        print("✅ CONFIRMED SUBSCRIBERS:")
        print("-" * 80)
        for email, _, subscribed_at, confirmed_at, ip in confirmed:
            print(f"  • {email}")
            print(f"    Subscribed: {subscribed_at}")
            print(f"    Confirmed:  {confirmed_at}")
            if ip:
                print(f"    IP: {ip}")
            print()
    
    # Display pending subscribers
    pending = [s for s in all_subscribers if not s[1]]
    if pending:
        print("\n⏳ PENDING CONFIRMATIONS:")
        print("-" * 80)
        for email, _, subscribed_at, _, ip in pending:
            print(f"  • {email}")
            print(f"    Subscribed: {subscribed_at}")
            print(f"    Status: Awaiting confirmation")
            if ip:
                print(f"    IP: {ip}")
            print()
    
    print("="*80 + "\n")

def export_confirmed_emails():
    """Export just the confirmed email addresses (one per line)"""
    subscribers = get_all_confirmed_subscribers()
    
    if not subscribers:
        print("\n📭 No confirmed subscribers yet.\n")
        return
    
    print("\n📧 CONFIRMED EMAIL ADDRESSES:\n")
    for _, email, _, _ in subscribers:
        print(email)
    print()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--emails-only":
        export_confirmed_emails()
    else:
        view_all_subscribers()

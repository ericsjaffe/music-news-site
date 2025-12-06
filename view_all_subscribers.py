#!/usr/bin/env python3
"""
View all SMS and Email subscribers
"""
from newsletter_db import get_all_confirmed_subscribers, get_subscriber_count
from sms_db import get_all_confirmed_sms_subscribers, get_sms_subscriber_count
import sqlite3

def view_all():
    """Display all subscribers (email and SMS)"""
    
    print("\n" + "="*80)
    print("📧 EMAIL SUBSCRIBERS")
    print("="*80)
    
    # Email stats
    email_stats = get_subscriber_count()
    print(f"✅ Confirmed: {email_stats.get('confirmed', email_stats.get('confirmed_subscribers', 0))}")
    print(f"⏳ Pending:   {email_stats.get('pending', email_stats.get('pending_confirmations', 0))}")
    print(f"📊 Total:     {email_stats.get('total', 0)}")
    
    # Show all email subscribers
    conn = sqlite3.connect('newsletter_subscribers.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT email, confirmed, subscribed_at, confirmed_at
        FROM subscribers
        ORDER BY subscribed_at DESC
    """)
    emails = cursor.fetchall()
    conn.close()
    
    if emails:
        print("\n" + "-"*80)
        for email, confirmed, subscribed_at, confirmed_at in emails:
            status = "✅ Confirmed" if confirmed else "⏳ Pending"
            print(f"{status} | {email}")
            print(f"           Subscribed: {subscribed_at}")
            if confirmed_at:
                print(f"           Confirmed:  {confirmed_at}")
            print()
    
    print("\n" + "="*80)
    print("📱 SMS SUBSCRIBERS")
    print("="*80)
    
    # SMS stats
    sms_stats = get_sms_subscriber_count()
    print(f"✅ Confirmed: {sms_stats['confirmed_subscribers']}")
    print(f"⏳ Pending:   {sms_stats['pending_confirmations']}")
    print(f"📊 Total:     {sms_stats['total']}")
    
    # Show all SMS subscribers
    conn = sqlite3.connect('sms_subscribers.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT phone_number, confirmed, subscribed_at, confirmed_at
        FROM sms_subscribers
        ORDER BY subscribed_at DESC
    """)
    phones = cursor.fetchall()
    conn.close()
    
    if phones:
        print("\n" + "-"*80)
        for phone, confirmed, subscribed_at, confirmed_at in phones:
            status = "✅ Confirmed" if confirmed else "⏳ Pending"
            print(f"{status} | {phone}")
            print(f"           Subscribed: {subscribed_at}")
            if confirmed_at:
                print(f"           Confirmed:  {confirmed_at}")
            print()
    
    print("="*80 + "\n")

if __name__ == "__main__":
    view_all()

#!/usr/bin/env python3
"""
Clear all pending (unconfirmed) subscribers from databases
"""
import sqlite3

def clear_pending_subscribers():
    """Remove all pending subscribers from both email and SMS databases"""
    
    # Clear pending email subscribers
    try:
        conn = sqlite3.connect('newsletter_subscribers.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM subscribers WHERE confirmed = FALSE")
        email_deleted = cursor.rowcount
        conn.commit()
        conn.close()
        print(f"✅ Deleted {email_deleted} pending email subscribers")
    except Exception as e:
        print(f"❌ Error clearing email subscribers: {e}")
    
    # Clear pending SMS subscribers
    try:
        conn = sqlite3.connect('sms_subscribers.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sms_subscribers WHERE confirmed = FALSE")
        sms_deleted = cursor.rowcount
        conn.commit()
        conn.close()
        print(f"✅ Deleted {sms_deleted} pending SMS subscribers")
    except Exception as e:
        print(f"❌ Error clearing SMS subscribers: {e}")
    
    print("\n✨ All pending subscribers cleared!")

if __name__ == "__main__":
    confirm = input("⚠️  This will delete all PENDING subscribers. Are you sure? (yes/no): ")
    if confirm.lower() == 'yes':
        clear_pending_subscribers()
    else:
        print("Cancelled.")

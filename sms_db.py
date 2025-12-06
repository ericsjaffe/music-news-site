"""
Database management for SMS subscribers
"""
import sqlite3
from datetime import datetime
import secrets
from typing import Dict, List, Tuple, Optional


def init_sms_db():
    """Initialize the SMS subscribers database."""
    conn = sqlite3.connect('sms_subscribers.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sms_subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE NOT NULL,
            confirmation_token TEXT UNIQUE NOT NULL,
            confirmed BOOLEAN DEFAULT FALSE,
            subscribed_at TEXT NOT NULL,
            confirmed_at TEXT,
            ip_address TEXT,
            user_agent TEXT
        )
    """)
    
    # Table to track sent article notifications (prevent duplicates)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sms_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_url TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            recipient_count INTEGER DEFAULT 0
        )
    """)
    
    conn.commit()
    conn.close()


def add_sms_subscriber(phone_number: str, ip_address: str = "", user_agent: str = "") -> Dict:
    """
    Add a new SMS subscriber to the database.
    Returns dict with success status and token.
    """
    conn = sqlite3.connect('sms_subscribers.db')
    cursor = conn.cursor()
    
    try:
        # Check if already exists
        cursor.execute("SELECT confirmed FROM sms_subscribers WHERE phone_number = ?", (phone_number,))
        existing = cursor.fetchone()
        
        if existing:
            if existing[0]:  # already confirmed
                conn.close()
                return {"success": False, "error": "already_subscribed"}
            else:  # pending confirmation - resend
                cursor.execute("SELECT confirmation_token FROM sms_subscribers WHERE phone_number = ?", (phone_number,))
                token = cursor.fetchone()[0]
                conn.close()
                return {"success": True, "token": token, "resend": True}
        
        # Generate unique confirmation token
        token = secrets.token_urlsafe(32)
        
        # Insert new subscriber
        cursor.execute("""
            INSERT INTO sms_subscribers (phone_number, confirmation_token, subscribed_at, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?)
        """, (phone_number, token, datetime.now().isoformat(), ip_address, user_agent))
        
        conn.commit()
        conn.close()
        
        return {"success": True, "token": token, "resend": False}
    
    except Exception as e:
        conn.close()
        print(f"Error adding SMS subscriber: {e}")
        return {"success": False, "error": str(e)}


def confirm_sms_subscriber(token: str) -> bool:
    """Confirm an SMS subscriber using their token."""
    conn = sqlite3.connect('sms_subscribers.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE sms_subscribers 
            SET confirmed = TRUE, confirmed_at = ?
            WHERE confirmation_token = ? AND confirmed = FALSE
        """, (datetime.now().isoformat(), token))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    except Exception as e:
        conn.close()
        print(f"Error confirming SMS subscriber: {e}")
        return False


def is_sms_confirmed(phone_number: str) -> bool:
    """Check if a phone number is confirmed."""
    conn = sqlite3.connect('sms_subscribers.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT confirmed FROM sms_subscribers WHERE phone_number = ?", (phone_number,))
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else False


def get_sms_confirmation_token(phone_number: str) -> Optional[str]:
    """Get confirmation token for a phone number."""
    conn = sqlite3.connect('sms_subscribers.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT confirmation_token FROM sms_subscribers WHERE phone_number = ?", (phone_number,))
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else None


def get_all_confirmed_sms_subscribers() -> List[Tuple[int, str, str, str]]:
    """Get all confirmed SMS subscribers."""
    conn = sqlite3.connect('sms_subscribers.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, phone_number, subscribed_at, confirmed_at
        FROM sms_subscribers
        WHERE confirmed = TRUE
        ORDER BY confirmed_at DESC
    """)
    
    subscribers = cursor.fetchall()
    conn.close()
    
    return subscribers


def unsubscribe_sms(phone_number: str) -> bool:
    """Remove an SMS subscriber."""
    conn = sqlite3.connect('sms_subscribers.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM sms_subscribers WHERE phone_number = ?", (phone_number,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    except Exception as e:
        conn.close()
        print(f"Error unsubscribing SMS: {e}")
        return False


def get_sms_subscriber_count() -> Dict[str, int]:
    """Get count of SMS subscribers by status."""
    conn = sqlite3.connect('sms_subscribers.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM sms_subscribers WHERE confirmed = TRUE")
    confirmed = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM sms_subscribers WHERE confirmed = FALSE")
    pending = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "confirmed_subscribers": confirmed,
        "pending_confirmations": pending,
        "total": confirmed + pending
    }


def article_already_sent(article_url: str) -> bool:
    """Check if an article notification has already been sent."""
    conn = sqlite3.connect('sms_subscribers.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM sms_notifications WHERE article_url = ?", (article_url,))
    result = cursor.fetchone()
    conn.close()
    
    return result is not None


def mark_article_sent(article_url: str, recipient_count: int):
    """Mark an article as having been sent to subscribers."""
    conn = sqlite3.connect('sms_subscribers.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO sms_notifications (article_url, sent_at, recipient_count)
        VALUES (?, ?, ?)
    """, (article_url, datetime.now().isoformat(), recipient_count))
    
    conn.commit()
    conn.close()


# Initialize database on import
init_sms_db()

"""
Database management for newsletter subscriptions.
"""
import sqlite3
from datetime import datetime
import secrets


DB_PATH = "newsletter_subscribers.db"


def init_newsletter_db():
    """Initialize the newsletter subscribers database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            confirmation_token TEXT UNIQUE NOT NULL,
            confirmed BOOLEAN DEFAULT FALSE,
            subscribed_at TEXT NOT NULL,
            confirmed_at TEXT,
            ip_address TEXT,
            user_agent TEXT
        )
    """)
    
    conn.commit()
    conn.close()


def add_subscriber(email: str, ip_address: str = None, user_agent: str = None) -> dict:
    """
    Add a new subscriber to the database.
    Returns dict with success status and token.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Generate unique confirmation token
    token = secrets.token_urlsafe(32)
    timestamp = datetime.utcnow().isoformat()
    
    try:
        cursor.execute("""
            INSERT INTO subscribers (email, confirmation_token, subscribed_at, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?)
        """, (email, token, timestamp, ip_address, user_agent))
        
        conn.commit()
        subscriber_id = cursor.lastrowid
        conn.close()
        
        return {
            "success": True,
            "id": subscriber_id,
            "token": token,
            "message": "Subscriber added successfully"
        }
    except sqlite3.IntegrityError:
        conn.close()
        # Check if already confirmed
        confirmed = is_confirmed(email)
        if confirmed:
            return {
                "success": False,
                "error": "already_subscribed",
                "message": "This email is already subscribed"
            }
        else:
            # Get existing token to resend confirmation
            existing_token = get_confirmation_token(email)
            return {
                "success": True,
                "resend": True,
                "token": existing_token,
                "message": "Confirmation email resent"
            }


def confirm_subscriber(token: str) -> bool:
    """Confirm a subscriber using their token."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    timestamp = datetime.utcnow().isoformat()
    
    cursor.execute("""
        UPDATE subscribers 
        SET confirmed = TRUE, confirmed_at = ?
        WHERE confirmation_token = ? AND confirmed = FALSE
    """, (timestamp, token))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return success


def is_confirmed(email: str) -> bool:
    """Check if an email is already confirmed."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT confirmed FROM subscribers WHERE email = ?
    """, (email,))
    
    result = cursor.fetchone()
    conn.close()
    
    return result and result[0]


def get_confirmation_token(email: str) -> str | None:
    """Get the confirmation token for an email."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT confirmation_token FROM subscribers WHERE email = ?
    """, (email,))
    
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else None


def get_all_confirmed_subscribers():
    """Get all confirmed subscribers."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, email, subscribed_at, confirmed_at 
        FROM subscribers 
        WHERE confirmed = TRUE
        ORDER BY confirmed_at DESC
    """)
    
    subscribers = cursor.fetchall()
    conn.close()
    
    return subscribers


def unsubscribe(email: str) -> bool:
    """Remove a subscriber from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM subscribers WHERE email = ?", (email,))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return success


def get_subscriber_count() -> dict:
    """Get subscriber statistics."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM subscribers WHERE confirmed = TRUE")
    confirmed = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM subscribers WHERE confirmed = FALSE")
    pending = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "confirmed": confirmed,
        "pending": pending,
        "total": confirmed + pending
    }

# Newsletter Email System Setup

## Overview

The Music Hub newsletter system now includes:
- ✅ **Email storage** in SQLite database (`newsletter_subscribers.db`)
- ✅ **Double opt-in** confirmation via email
- ✅ **Confirmation emails** with branded HTML templates
- ✅ **Unsubscribe functionality**
- ✅ **Subscriber statistics** endpoint

## Database Storage

Emails are stored in `newsletter_subscribers.db` with the following information:
- Email address
- Confirmation token (unique, secure)
- Subscription status (pending/confirmed)
- Timestamps (subscribed_at, confirmed_at)
- IP address and User Agent (for security)

### Database Schema
```sql
CREATE TABLE subscribers (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    confirmation_token TEXT UNIQUE NOT NULL,
    confirmed BOOLEAN DEFAULT FALSE,
    subscribed_at TEXT NOT NULL,
    confirmed_at TEXT,
    ip_address TEXT,
    user_agent TEXT
)
```

## Email Confirmation Flow

1. **User subscribes** via newsletter form on homepage
2. **Email saved** to database with unique confirmation token
3. **Confirmation email sent** with clickable link
4. **User clicks link** → `/newsletter/confirm/{token}`
5. **Subscription confirmed** → User can now receive newsletters
6. **Confirmation page shown** with success message

## Email Configuration

### Option 1: Gmail (Recommended for Testing)

1. Enable 2-Factor Authentication on your Google account
2. Generate an App Password: https://myaccount.google.com/apppasswords
3. Update `app.py` lines 36-39:

```python
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "your-email@gmail.com"
SMTP_PASSWORD = "your-16-char-app-password"
FROM_EMAIL = "Music Hub <your-email@gmail.com>"
```

### Option 2: SendGrid (Recommended for Production)

```bash
pip install sendgrid
```

Update email sending code to use SendGrid API:
```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# In send_confirmation_email():
message = Mail(
    from_email='noreply@yourdomain.com',
    to_emails=email,
    subject='Confirm your Music Hub Newsletter Subscription',
    html_content=html
)
sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
sg.send(message)
```

### Option 3: Mailgun

```python
import requests

def send_via_mailgun(email, html, text):
    return requests.post(
        "https://api.mailgun.net/v3/YOUR_DOMAIN/messages",
        auth=("api", "YOUR_API_KEY"),
        data={
            "from": "Music Hub <noreply@yourdomain.com>",
            "to": email,
            "subject": "Confirm your Music Hub Newsletter Subscription",
            "text": text,
            "html": html
        }
    )
```

## Current Behavior (No SMTP Configured)

If SMTP credentials are not configured:
- ✅ Emails are still **saved to database**
- ✅ Confirmation tokens are generated
- ⚠️ Confirmation emails are **not sent** (skipped)
- ✅ Token is printed to console for testing
- ✅ Users can still be manually confirmed in database

## Testing Without Email

You can test the system without configuring email:

1. User subscribes → email saved to database
2. Check terminal output for confirmation token
3. Manually visit: `http://localhost:5001/newsletter/confirm/{TOKEN}`
4. User is confirmed

## Available Endpoints

### User-Facing
- `POST /newsletter/subscribe` - Subscribe to newsletter
- `GET /newsletter/confirm/<token>` - Confirm subscription via email link
- `GET /newsletter/unsubscribe` - Unsubscribe page
- `POST /newsletter/unsubscribe` - Process unsubscription

### Admin
- `GET /newsletter/stats` - View subscriber statistics
  ```json
  {
    "confirmed_subscribers": 42,
    "pending_confirmations": 5,
    "total": 47
  }
  ```

## Viewing Subscribers

To view all confirmed subscribers, you can query the database:

```bash
sqlite3 newsletter_subscribers.db "SELECT email, confirmed_at FROM subscribers WHERE confirmed = TRUE;"
```

Or use Python:
```python
from newsletter_db import get_all_confirmed_subscribers

subscribers = get_all_confirmed_subscribers()
for sub_id, email, subscribed_at, confirmed_at in subscribers:
    print(f"{email} - Confirmed: {confirmed_at}")
```

## Security Features

- ✅ Unique confirmation tokens (cryptographically secure)
- ✅ Double opt-in (prevents spam subscriptions)
- ✅ Email validation
- ✅ Duplicate prevention
- ✅ IP address tracking (for abuse prevention)
- ✅ One-click unsubscribe

## Email Template

The confirmation email includes:
- Branded header with gradient (pink theme)
- Clear call-to-action button
- Plain text fallback
- Unsubscribe information
- Professional HTML design

## Sending Newsletters

Once you have confirmed subscribers, you can send newsletters with:

```python
from newsletter_db import get_all_confirmed_subscribers

subscribers = get_all_confirmed_subscribers()

for sub_id, email, subscribed_at, confirmed_at in subscribers:
    # Send your newsletter to 'email'
    send_newsletter_email(email, newsletter_content)
```

## Production Recommendations

1. **Use a dedicated email service** (SendGrid, Mailgun, AWS SES)
2. **Add rate limiting** to prevent abuse
3. **Monitor bounce rates** and remove invalid emails
4. **Include unsubscribe link** in every newsletter
5. **Comply with CAN-SPAM Act** and GDPR
6. **Use a custom domain** for professional from addresses
7. **Set up SPF, DKIM, DMARC** records for deliverability

## Environment Variables (Production)

Store sensitive credentials in environment variables:

```bash
export SMTP_SERVER="smtp.gmail.com"
export SMTP_USERNAME="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
export FROM_EMAIL="Music Hub <noreply@musichub.com>"
```

Update app.py:
```python
import os
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'noreply@musichub.com')
```

## Files Modified/Created

- `newsletter_db.py` - Database management for subscribers
- `app.py` - Updated with email sending and confirmation routes
- `templates/newsletter_confirm.html` - Confirmation success/failure page
- `templates/newsletter_unsubscribe.html` - Unsubscribe page
- `newsletter_subscribers.db` - SQLite database (auto-created)
- `NEWSLETTER_SETUP.md` - This documentation

## Questions?

- Emails stored in: `newsletter_subscribers.db`
- Confirmation: Double opt-in via email link
- SMTP: Configure in `app.py` lines 36-39
- Testing: Tokens printed to console if SMTP not configured

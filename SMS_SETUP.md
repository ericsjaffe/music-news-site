# SMS Notifications Setup Guide

## Overview

The Music Hub now includes SMS text message notifications! Users can subscribe to receive instant alerts whenever new music articles are published.

## Features

✅ **SMS Signup Form** - Users enter their phone number  
✅ **Double Opt-In** - Confirmation link sent via SMS  
✅ **Auto Notifications** - Text alerts for new articles  
✅ **Admin Notifications** - Get alerted when someone subscribes  
✅ **Easy Unsubscribe** - Reply STOP or visit unsubscribe page  
✅ **Duplicate Prevention** - Won't send same article twice  

## Setup Instructions

### 1. Install Twilio Package

```bash
pip install twilio
```

### 2. Create Twilio Account

1. Go to [twilio.com](https://www.twilio.com) and sign up
2. Get a free trial account (includes $15 credit)
3. Buy a phone number (or use trial number)
4. Find your credentials in the [Twilio Console](https://console.twilio.com):
   - **Account SID** (starts with "AC...")
   - **Auth Token** (secret key)
   - **Phone Number** (your Twilio number, format: +1234567890)

### 3. Configure app.py

Update lines 42-45 in `app.py`:

```python
TWILIO_ACCOUNT_SID = "AC..."  # Your Account SID
TWILIO_AUTH_TOKEN = "your_auth_token_here"
TWILIO_PHONE_NUMBER = "+15551234567"  # Your Twilio number
ADMIN_PHONE = "+15559876543"  # Your personal number for admin alerts
```

### 4. Test the System

Start your Flask app:
```bash
python app.py
```

Visit `http://localhost:5001` and test:
1. Enter phone number in SMS signup form
2. You should receive confirmation SMS
3. Click the link in the SMS
4. You're subscribed!

### 5. Run Article Monitoring (Production)

The monitoring script checks for new articles and sends SMS alerts:

**Option A: Manual Run**
```bash
python send_article_notifications.py
```

**Option B: Background Process (Recommended)**
```bash
nohup python send_article_notifications.py > sms_notifications.log 2>&1 &
```

**Option C: System Service (systemd)**

Create `/etc/systemd/system/music-hub-sms.service`:
```ini
[Unit]
Description=Music Hub SMS Notifications
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/music-news-site
ExecStart=/usr/bin/python3 send_article_notifications.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable music-hub-sms
sudo systemctl start music-hub-sms
sudo systemctl status music-hub-sms
```

### 6. Update Site URL (Production)

In `send_article_notifications.py`, change line 23:
```python
SITE_URL = "https://yoursite.com"  # Your actual domain
```

## How It Works

### User Flow

1. **Signup**: User enters phone number on homepage
2. **Confirmation**: Receives SMS with confirmation link
3. **Confirmed**: Clicks link → subscription activated
4. **Notifications**: Receives SMS for each new article
5. **Unsubscribe**: Reply STOP or visit `/sms/unsubscribe`

### Article Notification Flow

1. `send_article_notifications.py` runs in background
2. Checks RSS feed every 5 minutes for new articles
3. Compares with database of sent notifications
4. Sends SMS to all confirmed subscribers
5. Marks article as sent to prevent duplicates

## Database

SMS subscribers stored in `sms_subscribers.db`:

### Tables

**sms_subscribers**
- `phone_number` - Subscriber's phone (unique)
- `confirmation_token` - Unique token for confirmation
- `confirmed` - Boolean (TRUE after confirmation)
- `subscribed_at` - Timestamp
- `confirmed_at` - Confirmation timestamp
- `ip_address` - For security/tracking
- `user_agent` - Browser info

**sms_notifications**
- `article_url` - URL of sent article
- `sent_at` - When notification was sent
- `recipient_count` - Number of recipients

## Available Endpoints

### User Endpoints
- `POST /sms/subscribe` - Subscribe to SMS alerts
- `GET /sms/confirm/<token>` - Confirm subscription
- `GET /sms/unsubscribe` - Unsubscribe form
- `POST /sms/unsubscribe` - Process unsubscription

### Admin Endpoints
- `GET /sms/stats` - View subscriber statistics

## View Subscribers

Create a viewer script similar to `view_subscribers.py`:

```bash
python -c "from sms_db import get_all_confirmed_sms_subscribers; subscribers = get_all_confirmed_sms_subscribers(); print(f'Confirmed SMS subscribers: {len(subscribers)}'); [print(phone) for _, phone, _, _ in subscribers]"
```

Or query directly:
```bash
sqlite3 sms_subscribers.db "SELECT phone_number, confirmed, confirmed_at FROM sms_subscribers;"
```

## Cost Estimates

### Twilio Pricing (as of 2024)
- **SMS (US/Canada)**: $0.0079 per message
- **Monthly phone number**: $1.15/month
- **100 subscribers × 10 articles/month**: ~$8/month

### Free Trial
- $15 credit included
- Test numbers only
- "Sent from Twilio trial account" prepended to messages

## Compliance & Best Practices

### Legal Requirements
✅ Double opt-in (confirmation required)  
✅ Easy unsubscribe (STOP keyword)  
✅ Clear messaging about text frequency  
✅ Rate limiting to prevent spam  

### Message Content Guidelines
- Keep under 160 characters when possible
- Include unsubscribe instructions
- Don't send too frequently (5min minimum between checks)
- Provide value in each message

### TCPA Compliance
- Get explicit consent before texting
- Honor opt-out requests immediately
- Keep records of consent
- Don't share phone numbers

## Troubleshooting

### SMS Not Sending

**Check Twilio Configuration:**
```python
# In app.py, temporarily add:
print(f"Twilio SID: {TWILIO_ACCOUNT_SID[:10]}...")
print(f"Phone: {TWILIO_PHONE_NUMBER}")
```

**Check Twilio Console:**
- Visit [console.twilio.com](https://console.twilio.com)
- Check "Monitor" → "Logs" → "Errors"
- Verify phone number status

**Common Issues:**
- Invalid phone number format (must include +1 for US)
- Trial account restrictions (can only text verified numbers)
- Insufficient balance
- Blocked number

### No New Articles Detected

**Check Feed:**
```bash
curl https://loudwire.com/category/news/feed
```

**Check Monitoring Script:**
```bash
python send_article_notifications.py
# Watch for errors in output
```

**Check Database:**
```bash
sqlite3 sms_subscribers.db "SELECT COUNT(*) FROM sms_notifications;"
# Shows how many articles have been sent
```

### Subscriber Count Zero

**Check Database:**
```bash
sqlite3 sms_subscribers.db "SELECT phone_number, confirmed FROM sms_subscribers;"
```

**Re-initialize Database:**
```bash
python -c "from sms_db import init_sms_db; init_sms_db(); print('Database initialized')"
```

## Production Deployment

### Environment Variables (Recommended)

Instead of hardcoding credentials, use environment variables:

```python
# In app.py:
import os
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', 'your-account-sid')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', 'your-auth-token')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '+1234567890')
ADMIN_PHONE = os.getenv('ADMIN_PHONE', '+1234567890')
```

Set in production:
```bash
export TWILIO_ACCOUNT_SID="ACxxxxx"
export TWILIO_AUTH_TOKEN="xxxxx"
export TWILIO_PHONE_NUMBER="+15551234567"
export ADMIN_PHONE="+15559876543"
```

### Rate Limiting

Add rate limiting to prevent abuse:

```python
from flask_limiter import Limiter

limiter = Limiter(app, key_func=lambda: request.remote_addr)

@app.route("/sms/subscribe", methods=["POST"])
@limiter.limit("5 per hour")  # Max 5 signups per IP per hour
def sms_subscribe():
    # ... existing code
```

### Monitoring

Monitor the notification script:
```bash
tail -f sms_notifications.log
```

Set up alerts if process stops:
```bash
# Check if running
ps aux | grep send_article_notifications.py
```

## Alternative Services

Besides Twilio, you can use:

- **MessageBird** - Global coverage
- **Vonage (Nexmo)** - Reliable API
- **AWS SNS** - Integrated with AWS
- **Plivo** - Competitive pricing
- **Bandwidth** - Enterprise solution

## Future Enhancements

Potential additions:
- Frequency preferences (instant, daily digest, weekly)
- Topic filtering (subscribe to specific genres/artists)
- Custom notification times
- Multimedia messages (MMS with images)
- Two-way messaging (reply to articles)
- Delivery reports and analytics
- A/B testing for message content

## Support

If you encounter issues:
1. Check Twilio console logs
2. Review `sms_notifications.log`
3. Test with your own number first
4. Verify database entries with sqlite3
5. Check Flask app logs

## Files Created

- `sms_db.py` - SMS subscriber database management
- `send_article_notifications.py` - Background monitoring script
- `templates/sms_confirm.html` - Confirmation page
- `templates/sms_unsubscribe.html` - Unsubscribe page
- `SMS_SETUP.md` - This documentation

## Quick Start Checklist

- [ ] Install Twilio: `pip install twilio`
- [ ] Create Twilio account and get credentials
- [ ] Update `app.py` with Twilio credentials
- [ ] Test SMS signup on homepage
- [ ] Confirm via SMS link
- [ ] Update `SITE_URL` in monitoring script
- [ ] Run `python send_article_notifications.py`
- [ ] Post a test article or wait for new RSS items
- [ ] Verify SMS received
- [ ] Set up background service for production

---

**Ready to go live?** Make sure to upgrade from Twilio trial to paid account to text any number!

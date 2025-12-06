# Keep-Alive Service

This service prevents your Render free tier instance from spinning down due to inactivity.

## How It Works

The `keep_alive.py` script pings your site every 10 minutes to keep it active.

## Option 1: Run Locally (Recommended for Testing)

Run this on your local machine:

```bash
python keep_alive.py
```

Keep this terminal window open. The script will run continuously.

## Option 2: Run on a Server

You can run this on any always-on server (VPS, Raspberry Pi, etc.):

```bash
# Install as a background service
nohup python3 keep_alive.py > keepalive.log 2>&1 &
```

## Option 3: Use External Services

Instead of running this script, you can use free external monitoring services:

### UptimeRobot (Recommended)
1. Sign up at https://uptimerobot.com (free)
2. Add a new monitor:
   - Monitor Type: HTTP(s)
   - URL: https://music-news-site.onrender.com
   - Monitoring Interval: 5 minutes
3. Save - it will automatically ping your site every 5 minutes

### Cron-job.org
1. Sign up at https://cron-job.org (free)
2. Create a new cron job:
   - URL: https://music-news-site.onrender.com
   - Execution schedule: */10 * * * * (every 10 minutes)
3. Save and enable

### Better Stack (formerly StatusCake)
1. Sign up at https://betterstack.com (free tier available)
2. Add uptime monitoring for your site
3. Set check interval to 5-10 minutes

## Note

Render's free tier spins down after 15 minutes of inactivity. By pinging every 10 minutes, the site stays active. However, there are still some limitations:
- Free instances have 750 hours/month limit
- After the monthly limit, the site will still spin down

For production use, consider upgrading to Render's paid tier ($7/month) which keeps your site always running.

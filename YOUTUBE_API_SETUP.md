# YouTube API Setup Instructions

This guide walks you through obtaining a YouTube Data API v3 key and configuring it for the Music Hub video page.

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Sign in with your Google account
3. Click "Select a project" → "New Project"
4. Enter project name: `music-hub-videos` (or any name)
5. Click "Create"

## Step 2: Enable YouTube Data API v3

1. In the Google Cloud Console, ensure your new project is selected
2. Go to "APIs & Services" → "Library" (left sidebar)
3. Search for "YouTube Data API v3"
4. Click on "YouTube Data API v3"
5. Click "Enable"

## Step 3: Create API Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "API key"
3. Your API key will be created and displayed
4. **Important**: Copy this key immediately
5. (Optional) Click "Restrict Key" to add restrictions:
   - **Application restrictions**: HTTP referrers (if deploying to specific domain)
   - **API restrictions**: Select "YouTube Data API v3" only
   - This improves security by limiting where the key can be used

## Step 4: Configure API Key Locally (Development)

### macOS/Linux:
```bash
export YOUTUBE_API_KEY="your-api-key-here"
```

Or add to `~/.bashrc` or `~/.zshrc`:
```bash
echo 'export YOUTUBE_API_KEY="your-api-key-here"' >> ~/.zshrc
source ~/.zshrc
```

### Windows (Command Prompt):
```cmd
set YOUTUBE_API_KEY=your-api-key-here
```

### Windows (PowerShell):
```powershell
$env:YOUTUBE_API_KEY="your-api-key-here"
```

## Step 5: Configure API Key on Render (Production)

1. Go to your [Render Dashboard](https://dashboard.render.com/)
2. Select your `music-news-site` web service
3. Click "Environment" in the left sidebar
4. Click "Add Environment Variable"
5. Add:
   - **Key**: `YOUTUBE_API_KEY`
   - **Value**: Your YouTube API key (paste from Step 3)
6. Click "Save Changes"
7. Render will automatically redeploy with the new environment variable

## Step 6: Verify Setup

1. Visit your site's `/videos` page
2. You should see trending music videos displayed
3. Try searching for an artist (e.g., "Metallica")
4. Videos should load and be playable

## API Quota Information

### Free Tier Limits:
- **Daily quota**: 10,000 units
- **Search operation**: ~100 units per search
- **Videos list**: ~1 unit per request
- **Typical usage**: ~100 video searches or 1,000 trending requests per day

### Cost per operation:
- Trending videos page load: ~1 unit
- Video search: ~101 units (1 search + 100 for details)
- Average use case: 50-100 searches/day = well within free tier

### If you exceed quota:
- Videos page will show "No videos found" message
- No errors thrown, graceful degradation
- Quota resets daily at midnight Pacific Time
- Monitor usage in Google Cloud Console → "APIs & Services" → "Dashboard"

## Optional: Increase Quota

If you need more than 10,000 units/day:

1. Go to Google Cloud Console
2. Navigate to "APIs & Services" → "Quotas"
3. Find "YouTube Data API v3"
4. Request quota increase
5. Google typically approves increases for legitimate use cases

## Troubleshooting

### Videos not loading:
1. Check API key is set: `echo $YOUTUBE_API_KEY`
2. Verify key is enabled in Google Cloud Console
3. Check quota hasn't been exceeded
4. Look for errors in server logs

### "API key not valid" error:
1. Ensure key was copied correctly (no extra spaces)
2. Check API restrictions aren't blocking your domain
3. Verify YouTube Data API v3 is enabled

### Rate limiting:
- API key restrictions might limit requests per second
- Default limits are sufficient for most use cases
- If needed, implement caching in application code

## Security Best Practices

1. **Never commit API keys to git**: Use environment variables
2. **Restrict API key**: Add HTTP referrer restrictions for production domain
3. **Monitor usage**: Check Google Cloud Console regularly
4. **Rotate keys**: Consider rotating keys periodically
5. **Use separate keys**: Different keys for development and production

## Alternative: No API Key

Without a YouTube API key, the video page will:
- Show "No videos found" message
- Display search form
- Not fetch or display any videos
- Remain functional for other site features

The app gracefully handles missing API keys and won't crash.

## Cost Considerations

The YouTube Data API v3 is **free** for typical usage:
- Free tier covers most small to medium websites
- No credit card required for free tier
- Only pay if you need quota increases
- Standard rates: $0 for first 10K units/day

## Additional Resources

- [YouTube Data API Documentation](https://developers.google.com/youtube/v3)
- [API Quota Calculator](https://developers.google.com/youtube/v3/determine_quota_cost)
- [Google Cloud Console](https://console.cloud.google.com/)
- [Render Environment Variables Guide](https://render.com/docs/environment-variables)

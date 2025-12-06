# Music Hub

A consolidated Flask application that combines music news aggregation, tour information, and music video discovery.

## Features

### 🎵 Music News
- Latest music news from Loudwire RSS feed
- Search functionality to filter articles by artist, genre, or keywords
- Clean card-based layout with images
- RSS feed parsing with deduplication

### 🎸 Touring & Concert Discovery
- Browse upcoming concerts and tours from Ticketmaster
- 7 specialized carousels: Trending, Coming Soon, Last Chance, Nearby Events, A-Z Guide, Random Discovery, Popular Venues
- Advanced filters: genre, date range, price range
- Artist following system with localStorage
- Social sharing (Facebook, Twitter, WhatsApp)
- Nationwide location search with market tabs
- "Recommended for You" personalized carousel

### 🎬 Music Videos
- Trending music videos powered by YouTube Data API v3
- Search for videos by artist or song
- Embedded YouTube player with modal
- View counts and upload dates
- Responsive grid layout

### 📅 On This Day in Music
- Discover music releases on any specific date across multiple years
- Powered by MusicBrainz API
- Search across year ranges (e.g., find all releases on November 22 from 1990-2025)
- View detailed release information with links to MusicBrainz

## Project Structure

```
music-news-site/
├── app.py                    # Main Flask application
├── dedupe.py                 # Article deduplication utilities
├── dedupe_example_usage.py   # Example of how to use dedupe functions
├── requirements.txt          # Python dependencies
├── Procfile                  # For deployment (Heroku/Render)
├── static/
│   ├── styles.css           # Unified styles
│   └── robots.txt           # SEO and AI crawler configuration
└── templates/
    ├── index.html           # News page
    ├── releases.html        # Releases page
    ├── touring.html         # Tours/concerts page
    ├── videos.html          # Music videos page
    ├── event_card.html      # Event card component
    └── venue_card.html      # Venue card component
```

## Installation

1. Clone the repository:
```bash
cd music-news-site
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure API Keys (optional but recommended):

   **YouTube Data API v3** (for videos page):
   - Visit [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing
   - Enable "YouTube Data API v3"
   - Create credentials (API key)
   - Set environment variable: `export YOUTUBE_API_KEY="your-api-key"`
   - Free tier: 10,000 quota units/day (sufficient for most use)

   **Ticketmaster Discovery API** (for touring page):
   - Visit [Ticketmaster Developer Portal](https://developer.ticketmaster.com/)
   - Create a free account and get an API key
   - Set environment variable: `export TICKETMASTER_API_KEY="your-api-key"`
   - Default API key is included but rate-limited

4. Run the application:
```bash
python app.py
```

5. Open your browser to `http://localhost:5000`

## Usage

### News Page
- Visit the home page to see the latest music news
- Use the search bar to filter articles by keywords
- Click on any article to read the full story

### Touring Page
- Navigate to `/touring` to browse upcoming concerts
- Use filters to narrow by genre, date range, or price
- Follow artists to see their events in "Your Artists" carousel
- Share events on social media
- Advanced search for multi-artist queries and venue-specific events

### Videos Page
- Navigate to `/videos` to watch trending music videos
- Use the search bar to find videos by artist or song
- Click any video thumbnail to play in modal
- **Note**: Requires YouTube API key for full functionality

### Releases Page
- Navigate to `/releases` or click "Releases" in the navigation
- Select a date using the date picker
- Enter a year range (keep it small for better performance, e.g., 1990-2010)
- Click "Find releases" to see all music releases on that date across those years

## API Attribution

- **News Feed**: Loudwire RSS
- **Concert Data**: Ticketmaster Discovery API v2
- **Video Data**: YouTube Data API v3
- **Release Data**: MusicBrainz API

## Deployment

The app includes a `Procfile` for easy deployment to platforms like Heroku or Render:

```
web: gunicorn app:app
```

## Technologies

- **Backend**: Flask (Python)
- **RSS Parsing**: feedparser
- **HTTP Requests**: requests
- **Styling**: Custom CSS with dark theme
- **APIs**: MusicBrainz REST API

## Features in Detail

### Deduplication
The app uses fuzzy string matching to deduplicate similar articles that might appear with slightly different headlines across different sources.

### Rate Limiting
The MusicBrainz integration includes polite rate limiting (0.1s delay between requests) to respect their API guidelines.

### Responsive Design
Both pages are fully responsive and work well on mobile devices.

## Notes

- The MusicBrainz API has a limit on year ranges (max 25 years per request) to prevent timeouts
- The search functionality on the news page filters locally from the RSS feed
- Images are cached and have fallback handling for broken links

## License

MIT

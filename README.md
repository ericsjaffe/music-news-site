# Music Hub

A consolidated Flask application that combines music news aggregation with music release discovery.

## Features

### 🎵 Music News
- Latest music news from Loudwire RSS feed
- Search functionality to filter articles by artist, genre, or keywords
- Clean card-based layout with images
- RSS feed parsing with deduplication

### 📅 On This Day in Music
- Discover music releases on any specific date across multiple years
- Powered by MusicBrainz API
- Search across year ranges (e.g., find all releases on November 22 from 1990-2025)
- View detailed release information with links to MusicBrainz

## Project Structure

```
music-news-site/
├── app.py                    # Main Flask application with both routes
├── dedupe.py                 # Article deduplication utilities
├── dedupe_example_usage.py   # Example of how to use dedupe functions
├── requirements.txt          # Python dependencies
├── Procfile                  # For deployment (Heroku/Render)
├── static/
│   └── styles.css           # Unified styles for both pages
└── templates/
    ├── index.html           # News page template
    └── releases.html        # Releases page template
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

3. Run the application:
```bash
python app.py
```

4. Open your browser to `http://localhost:5001`

## Usage

### News Page
- Visit the home page to see the latest music news
- Use the search bar to filter articles by keywords
- Click on any article to read the full story

### Releases Page
- Navigate to `/releases` or click "Releases" in the navigation
- Select a date using the date picker
- Enter a year range (keep it small for better performance, e.g., 1990-2010)
- Click "Find releases" to see all music releases on that date across those years

## API Attribution

- **News Feed**: Loudwire RSS
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

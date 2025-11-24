"""
Example usage of the dedupe helpers in a Flask-style backend.

This is NOT meant to replace your whole backend – just to show
where to plug the dedupe step in.

Key bit you want is:

    from dedupe import dedupe_articles_fuzzy

    articles = fetch_all_music_news()
    articles = dedupe_articles_fuzzy(articles)

You can copy that pattern into your real route / handler.
"""

from typing import List, Dict, Any

from dedupe import dedupe_articles_fuzzy


def fetch_all_music_news() -> List[Dict[str, Any]]:
    """
    Placeholder: in your app this will aggregate results from
    NewsAPI, GNews, Custom API, etc.
    """
    # Example dummy data to show de-duplication:
    return [
        {
            "title": "Donald Glover reveals he cancelled tour due to stroke",
            "source": "TheWrap",
        },
        {
            "title": "Donald Glover discloses terrifying health issue that forced him to cancel tour",
            "source": "Page Six",
        },
        {
            "title": "Sami Valimaki wins RSM Classic, first Finnish winner on the PGA Tour",
            "source": "USA Today",
        },
    ]


def get_deduped_articles() -> List[Dict[str, Any]]:
    """
    Call this from your API route / view.
    """
    articles = fetch_all_music_news()
    articles = dedupe_articles_fuzzy(articles, threshold=0.86)
    return articles


if __name__ == "__main__":
    # Quick sanity check when running locally:
    from pprint import pprint

    pprint(get_deduped_articles())

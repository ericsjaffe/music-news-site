import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

DB_FILE = "releases_cache.db"
CACHE_EXPIRY_DAYS = 30  # Cache results for 30 days

def init_db():
    """Initialize the cache database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS release_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mm_dd TEXT NOT NULL,
            start_year INTEGER NOT NULL,
            end_year INTEGER NOT NULL,
            results_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(mm_dd, start_year, end_year)
        )
    """)
    
    # Index for faster lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_cache_lookup 
        ON release_cache(mm_dd, start_year, end_year)
    """)
    
    conn.commit()
    conn.close()

def get_cached_results(mm_dd: str, start_year: int, end_year: int) -> Optional[List[Dict[str, Any]]]:
    """Retrieve cached results if they exist and aren't expired."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT results_json, created_at 
        FROM release_cache 
        WHERE mm_dd = ? AND start_year = ? AND end_year = ?
    """, (mm_dd, start_year, end_year))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    results_json, created_at_str = row
    
    # Check if cache is expired
    created_at = datetime.fromisoformat(created_at_str)
    expiry_date = created_at + timedelta(days=CACHE_EXPIRY_DAYS)
    
    if datetime.now() > expiry_date:
        # Cache expired, delete it
        delete_cached_results(mm_dd, start_year, end_year)
        return None
    
    # Return parsed results
    return json.loads(results_json)

def save_cached_results(mm_dd: str, start_year: int, end_year: int, results: List[Dict[str, Any]]):
    """Save search results to cache."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    results_json = json.dumps(results)
    created_at = datetime.now().isoformat()
    
    cursor.execute("""
        INSERT OR REPLACE INTO release_cache 
        (mm_dd, start_year, end_year, results_json, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (mm_dd, start_year, end_year, results_json, created_at))
    
    conn.commit()
    conn.close()

def delete_cached_results(mm_dd: str, start_year: int, end_year: int):
    """Delete specific cached results."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        DELETE FROM release_cache 
        WHERE mm_dd = ? AND start_year = ? AND end_year = ?
    """, (mm_dd, start_year, end_year))
    
    conn.commit()
    conn.close()

def cleanup_old_cache():
    """Remove all expired cache entries."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    expiry_date = (datetime.now() - timedelta(days=CACHE_EXPIRY_DAYS)).isoformat()
    
    cursor.execute("""
        DELETE FROM release_cache 
        WHERE created_at < ?
    """, (expiry_date,))
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    return deleted_count

def get_cache_stats() -> Dict[str, Any]:
    """Get statistics about the cache."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM release_cache")
    total_entries = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM release_cache 
        WHERE created_at >= ?
    """, ((datetime.now() - timedelta(days=7)).isoformat(),))
    recent_entries = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "total_entries": total_entries,
        "recent_entries": recent_entries,
        "cache_expiry_days": CACHE_EXPIRY_DAYS
    }

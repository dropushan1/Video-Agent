import sqlite3
import csv
import os
import config

def load_metadata():
    """
    Reads the metadata.csv and returns a dictionary of lists.
    Format: {'Category': [...], 'Tags': [...], 'Types': [...], 'Platform': [...]}
    """
    data = {'Category': [], 'Tags': [], 'Types': [], 'Platform': []}
    if not os.path.exists(config.CSV_PATH):
        print(f"Warning: Metadata CSV at {config.CSV_PATH} not found.")
        return data

    with open(config.CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            for key in data.keys():
                if row.get(key) and row[key].strip():
                    val = row[key].strip()
                    if val not in data[key]: # Avoid duplicates in list if any
                        data[key].append(val)
    return data

def search_videos_by_criteria(criteria):
    """
    Searches DB for videos matching the criteria (broad search).
    Criteria is a dict: {'category': [...], 'tags': [...], 'types': [...]} (lowercase keys from AI)
    Returns: List of dicts (id, title, summary, etc.)
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Construct dynamic query
    # We will use OR logic within fields (e.g. cat1 OR cat2)
    # AND logic between fields (Category AND Tags matches) - or Broad?
    # User said: "choose little broadly here... so it gets all the potential important info"
    # So I will use OR across everything to be broad?
    # "system will filter and output the best... system should always get of (Category,Tags,Types) from here only"
    # Let's try a query that matches ANY of the selected attributes.
    
    conditions = []
    params = []

    # Helper to build LIKE clauses
    def add_like_clauses(field_in_db, values):
        if not values:
            return
        # values is list of strings
        clauses = []
        for v in values:
            clauses.append(f"{field_in_db} LIKE ?")
            params.append(f"%{v}%")
        if clauses:
            conditions.append(f"({' OR '.join(clauses)})")

    add_like_clauses("category", criteria.get("category", []))
    add_like_clauses("tags", criteria.get("tags", []))
    add_like_clauses("types", criteria.get("types", []))

    if not conditions:
        # If no criteria returned, maybe return everything? Or nothing?
        # Let's return everything limit 100 to be safe, or just return all.
        sql = "SELECT id, title, summary, category, tags, types, refined_text FROM videos"
    else:
        # Combine with OR or AND?
        # Broad implementation: OR
        sql = "SELECT id, title, summary, category, tags, types, refined_text FROM videos WHERE " + " OR ".join(conditions)

    try:
        c.execute(sql, params)
        rows = c.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Database error: {e}")
        return []
    finally:
        conn.close()

def get_full_video_details(video_ids):
    """
    Fetch full details including refined_text for specific IDs.
    Returns: Dict mapping ID -> Video Dict
    """
    if not video_ids:
        return {}
    
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    placeholders = ', '.join(['?'] * len(video_ids))
    sql = f"SELECT * FROM videos WHERE id IN ({placeholders})"
    
    try:
        c.execute(sql, video_ids)
        rows = c.fetchall()
        return {row['id']: dict(row) for row in rows}
    except Exception as e:
        print(f"Database error: {e}")
        return {}
    finally:
        conn.close()

import functools
import time

# Simple cache for filter options
_filter_cache = {
    'data': None,
    'timestamp': 0
}
CACHE_DURATION = 300  # 5 minutes

def get_unique_filter_options():
    """
    Fetch unique values for platform, category, tags, and types for the gallery UI.
    Cached for CACHE_DURATION seconds.
    """
    global _filter_cache
    current_time = time.time()
    
    if _filter_cache['data'] and (current_time - _filter_cache['timestamp'] < CACHE_DURATION):
        return _filter_cache['data']

    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()
    
    options = {
        'platform': [],
        'category': [],
        'tags': [],
        'types': []
    }
    
    try:
        # Get platforms
        c.execute("SELECT DISTINCT platform FROM videos WHERE platform IS NOT NULL AND platform != ''")
        options['platform'] = [r[0] for r in c.fetchall()]
        
        # Get categories
        c.execute("SELECT DISTINCT category FROM videos WHERE category IS NOT NULL AND category != ''")
        options['category'] = [r[0] for r in c.fetchall()]
        
        # Get types
        c.execute("SELECT DISTINCT types FROM videos WHERE types IS NOT NULL AND types != ''")
        options['types'] = [r[0] for r in c.fetchall()]
        
        # For tags, we need to split by comma as they are often comma-separated strings
        c.execute("SELECT DISTINCT tags FROM videos WHERE tags IS NOT NULL AND tags != ''")
        all_tags = set()
        for row in c.fetchall():
            if row[0]:
                tags = [t.strip() for t in row[0].split(',') if t.strip()]
                all_tags.update(tags)
        options['tags'] = sorted(list(all_tags))
        
        _filter_cache['data'] = options
        _filter_cache['timestamp'] = current_time
        
        return options
    except Exception as e:
        print(f"Database error getting options: {e}")
        return options
    finally:
        conn.close()

def get_gallery_videos(filters, limit=50, offset=0):
    """
    Fetch videos based on multiple filter criteria.
    filters: {'platform': [], 'category': [], 'tags': [], 'types': []}
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Select only necessary columns for the gallery
    sql = "SELECT id, title, file_path, platform, category, tags, summary, types FROM videos"
    conditions = []
    params = []
    
    if filters.get('platform'):
        placeholders = ', '.join(['?'] * len(filters['platform']))
        conditions.append(f"platform IN ({placeholders})")
        params.extend(filters['platform'])
        
    if filters.get('category'):
        cat_conditions = []
        for cat in filters['category']:
            cat_conditions.append("category LIKE ?")
            params.append(f"%{cat}%")
        if cat_conditions:
            conditions.append(f"({' OR '.join(cat_conditions)})")
            
    if filters.get('types'):
        type_conditions = []
        for t in filters['types']:
            type_conditions.append("types LIKE ?")
            params.append(f"%{t}%")
        if type_conditions:
            conditions.append(f"({' OR '.join(type_conditions)})")
            
    if filters.get('tags'):
        tag_conditions = []
        for tag in filters['tags']:
            tag_conditions.append("tags LIKE ?")
            params.append(f"%{tag}%")
        if tag_conditions:
            conditions.append(f"({' OR '.join(tag_conditions)})")
            
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    
    # Order by ID or something consistent
    sql += " ORDER BY id DESC"
    
    # Add pagination
    sql += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    try:
        c.execute(sql, params)
        rows = c.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Database search error: {e}")
        return []
    finally:
        conn.close()

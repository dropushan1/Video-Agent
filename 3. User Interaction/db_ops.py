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

import sqlite3
import os

DB_NAME = "video_agent.db"

def inspect_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, title, raw_text FROM videos")
    rows = c.fetchall()
    
    print(f"Total Rows: {len(rows)}")
    seen_texts = {}
    
    for row in rows:
        vid, title, text = row
        print(f"ID: {vid} | Title: {title} | Text Length: {len(text)}")
        
        # Simple hash check
        text_hash = hash(text)
        if text_hash in seen_texts:
            print(f"   [!] DUPLICATE FOUND via Hash! Matches ID: {seen_texts[text_hash]}")
        seen_texts[text_hash] = vid
        
    conn.close()

if __name__ == "__main__":
    inspect_db()

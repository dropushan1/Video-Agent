import sqlite3
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(SCRIPT_DIR, "video_agent.db")

def migrate():
    if not os.path.exists(DB_NAME):
        print("Database not found. Nothing to migrate.")
        return

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    try:
        # 1. Create temporary table without 'link'
        c.execute("""CREATE TABLE videos_new (
            id TEXT PRIMARY KEY,
            title TEXT,
            summary TEXT,
            category TEXT,
            tags TEXT,
            types TEXT,
            refined_text TEXT,
            raw_text TEXT,
            platform TEXT,
            file_type TEXT,
            file_path TEXT,
            original_filename TEXT
        )""")
        
        # 2. Copy data (mapping only the existing columns)
        c.execute("""INSERT INTO videos_new (
            id, title, summary, category, tags, types, refined_text, 
            raw_text, platform, file_type, file_path, original_filename
        ) SELECT 
            id, title, summary, category, tags, types, refined_text, 
            raw_text, platform, file_type, file_path, original_filename
        FROM videos""")
        
        # 3. Drop old table and rename new one
        c.execute("DROP TABLE videos")
        c.execute("ALTER TABLE videos_new RENAME TO videos")
        
        conn.commit()
        print("✅ Migration successful: 'link' column removed.")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()

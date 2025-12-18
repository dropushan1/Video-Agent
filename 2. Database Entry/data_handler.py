import sqlite3
import csv
import os
import json
from google import genai
import itertools

# Config
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(SCRIPT_DIR, "video_agent.db")
CSV_PATH = os.path.join(SCRIPT_DIR, "metadata.csv")
PROMPT_PATH = os.path.join(SCRIPT_DIR, "Prompts/analysis_prompt.txt")
AI_KEY = "AIzaSyBg9la5eNcx4LzwB9uqj_QYBPNP0dn4ARA"

# Initialize AI Client
client = genai.Client(api_key=AI_KEY)

# --- Database ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS videos (
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
        file_path TEXT
    )""")
    conn.commit()
    conn.close()

def insert_record(record):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    placeholders = ', '.join(['?'] * len(record))
    columns = ', '.join(record.keys())
    sql = f"INSERT OR REPLACE INTO videos ({columns}) VALUES ({placeholders})"
    c.execute(sql, list(record.values()))
    conn.commit()
    conn.close()

def check_text_exists(raw_text):
    """
    Checks if a record with the same raw_text already exists.
    Returns True if exists, False otherwise.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id FROM videos WHERE raw_text = ? LIMIT 1", (raw_text,))
    result = c.fetchone()
    conn.close()
    return result is not None

# --- CSV Metadata (Columnar) ---
def load_metadata():
    """
    Returns dict: {'Category': [list], 'Tags': [list], 'Types': [list], 'Platform': [list]}
    """
    data = {'Category': [], 'Tags': [], 'Types': [], 'Platform': []}
    if not os.path.exists(CSV_PATH):
        return data
    
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            for key in data.keys():
                if row.get(key) and row[key].strip():
                    data[key].append(row[key].strip())
    return data

def save_new_metadata(col_name, value):
    """
    Adds value to the specified column and rewrites the CSV.
    col_name should be one of 'Category', 'Tags', 'Types', 'Platform'
    """
    current_data = load_metadata()
    
    # Check if duplicate
    if value in current_data.get(col_name, []):
        return

    # Add new val
    if col_name in current_data:
        current_data[col_name].append(value)
    else:
        # Fallback if somehow invalid col
        return

    # Rewrite CSV
    # 1. Determine max rows
    max_len = max(len(v) for v in current_data.values())
    
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Header
        headers = list(current_data.keys())
        writer.writerow(headers)
        
        # Rows
        for i in range(max_len):
            row = []
            for h in headers:
                if i < len(current_data[h]):
                    row.append(current_data[h][i])
                else:
                    row.append("")
            writer.writerow(row)

# --- AI Integration ---
def analyze_batch(items):
    """
    items: List of dicts [{'id':..., 'raw_text':..., 'platform':...}]
    """
    # 1. Load context
    meta = load_metadata()
    
    # Check prompt file exists
    if not os.path.exists(PROMPT_PATH):
        print(f"[Error] Prompt file not found at {PROMPT_PATH}")
        return []

    with open(PROMPT_PATH, 'r', encoding='utf-8') as f:
        prompt_template = f.read()
    
    # 2. Construct Prompt
    # Map the lists to the prompt placeholders
    # Note: Prompt template uses {categories}, {tags} etc. Need to match keys.
    prompt = prompt_template.replace("{categories}", ", ".join(meta['Category']))
    prompt = prompt.replace("{tags}", ", ".join(meta['Tags'])) # Key in CSV is 'Tags', Prompt uses {tags}
    prompt = prompt.replace("{types}", ", ".join(meta['Types'])) # Key in CSV is 'Types'
    prompt = prompt.replace("{items_json}", json.dumps(items, indent=2))

    # 3. Call AI
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview", 
            contents=prompt
        )
        text = response.text.strip()
        
        # Clean markdown
        if text.startswith("```json"): text = text[7:]
        if text.endswith("```"): text = text[:-3]
        
        return json.loads(text)
    except Exception as e:
        print(f"   [Error] AI Analysis failed: {e}")
        return []

import sqlite3
import csv
import os
import json
from google import genai
import itertools
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Config
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(SCRIPT_DIR, "video_agent.db")
CSV_PATH = os.path.join(SCRIPT_DIR, "metadata.csv")
PROMPT_PATH = os.path.join(SCRIPT_DIR, "Prompts/analysis_prompt.txt")

# Load API keys from environment
raw_keys = os.getenv("GEMINI_API_KEYS", "")
API_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

# Initialize AI Clients
clients = [genai.Client(api_key=key) for key in API_KEYS]
client_rotator = itertools.cycle(clients)

def get_unique_id():
    return str(uuid.uuid4())[:8]

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
        file_path TEXT,
        original_filename TEXT
    )""")
    # Migration: Add original_filename column if it doesn't exist
    try:
        c.execute("ALTER TABLE videos ADD COLUMN original_filename TEXT")
    except sqlite3.OperationalError:
        # Column already exists
        pass
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

def check_filename_exists(filename):
    """
    Checks if a record with the same original_filename already exists.
    Returns True if exists, False otherwise.
    """
    if not filename or not filename.strip():
        return False
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id FROM videos WHERE original_filename = ? LIMIT 1", (filename,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def check_text_exists(raw_text):
    """
    Checks if a record with the same raw_text already exists.
    Returns True if exists, False otherwise.
    """
    if not raw_text or not raw_text.strip():
        return False
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id FROM videos WHERE raw_text = ? LIMIT 1", (raw_text,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None


def get_existing_data(uid):
    """
    Returns (raw_text, refined_text) for a given ID.
    Used for Smart Resume.
    """
    if not uid:
        return None
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT raw_text, refined_text FROM videos WHERE id = ?", (uid,))
    result = c.fetchone()
    conn.close()
    return result

# --- CSV Metadata (Columnar) ---
def load_metadata():
    """
    Returns dict: {'Category': [list], 'Tags': [list], 'Types': [list], 'Platform': [list]}
    Handles wide CSV where columns may have different number of rows.
    """
    data = {'Category': [], 'Tags': [], 'Types': [], 'Platform': []}
    if not os.path.exists(CSV_PATH):
        return data
    
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            for key in data.keys():
                val = row.get(key)
                if val and val.strip():
                    data[key].append(val.strip())
    return data

def save_new_metadata(col_name, value):
    """
    Adds value to the specified column and rewrites the CSV.
    Performs case-insensitive duplicate check.
    """
    current_data = load_metadata()
    clean_val = value.strip()
    
    if not clean_val or col_name not in current_data:
        return

    # Case-insensitive check
    if any(v.lower() == clean_val.lower() for v in current_data[col_name]):
        return

    # Add new val
    current_data[col_name].append(clean_val)

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

    # 3. Call AI (Using rotated client)
    current_client = next(client_rotator)
    # For logging, find which index it is
    try:
        key_idx = clients.index(current_client) + 1
        print(f"      (Using API Key {key_idx}/3)")
    except:
        pass

    try:
        response = current_client.models.generate_content(
            model="gemini-3-flash-preview", 
            contents=prompt
        )
        
        # Extract text parts only to avoid 'thought_signature' warning
        text_parts = []
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.text:
                    text_parts.append(part.text)
        
        text = "".join(text_parts).strip()
        
        # Clean markdown
        if text.startswith("```json"): text = text[7:]
        if text.endswith("```"): text = text[:-3]
        
        return json.loads(text)
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
             raise RuntimeError("QUOTA_EXCEEDED")
        print(f"   [Error] AI Analysis failed: {e}")
        return []

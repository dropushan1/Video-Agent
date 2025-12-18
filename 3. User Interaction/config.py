import os

# Base paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)

# Database and Metadata Paths (Relative to this script)
DB_PATH = os.path.join(PARENT_DIR, "2. Database Entry", "video_agent.db")
CSV_PATH = os.path.join(PARENT_DIR, "2. Database Entry", "metadata.csv")

# Prompts Directory
PROMPTS_DIR = os.path.join(SCRIPT_DIR, "Prompts")

# API Configuration
# Note: Using the key found in existing data_handler.py
GOOGLE_API_KEY = "AIzaSyBg9la5eNcx4LzwB9uqj_QYBPNP0dn4ARA"
MODEL_NAME = "gemini-3-flash-preview"

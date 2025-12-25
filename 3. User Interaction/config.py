import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)

# Database and Metadata Paths (Relative to this script)
DB_PATH = os.path.join(PARENT_DIR, "2. Database Entry", "video_agent.db")
CSV_PATH = os.path.join(PARENT_DIR, "2. Database Entry", "metadata.csv")

# Prompts Directory
PROMPTS_DIR = os.path.join(SCRIPT_DIR, "Prompts")

# API Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_NAME = "gemini-3-flash-preview"

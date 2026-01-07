import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"
STATE_FILE = BASE_DIR / "state.json"

# API Configuration
SCOPES = [
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/calendar",
]

# Gemini Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Scheduling Configuration
SCHEDULE_DAYS_AHEAD = 14  # 2 weeks
DEFAULT_TASK_DURATION = 30 # minutes (fallback)

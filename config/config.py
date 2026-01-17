import os
from pathlib import Path

class Config:
    # Base Paths
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR / "data"
    CREDENTIALS_FILE = BASE_DIR / "credentials.json"
    TOKEN_FILE = DATA_DIR / "token.json"
    STATE_FILE = DATA_DIR / "state.json"

    # API Scopes
    SCOPES = [
        'https://www.googleapis.com/auth/tasks',
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events'
    ]

    # Task List Settings
    INBOX_LIST_NAME = "■メモ"
    TARGET_LIST_PREFIX = "■"

    # Gemini Settings
    # GEMINI_API_KEY should be set in environment variables or here
    GEMINI_API_KEY = "AIzaSyDeSl5IWOYOOlWO-tBONCBnOlUjXiZNsXw"

    # Calendar Settings
    # Default calendar ID (primary)
    CALENDAR_ID = "primary"
    
    # Scheduling Settings
    SCHEDULING_DAYS = 14  # Schedule up to 14 days ahead
    WORK_START_HOUR = 9
    WORK_END_HOUR = 19

    @classmethod
    def ensure_dirs(cls):
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)

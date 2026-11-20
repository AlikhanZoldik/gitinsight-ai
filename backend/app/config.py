import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
MAX_PAGES = 10
DETAIL_LIMIT = 8

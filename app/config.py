"""All settings in one place. Values come from environment variables (.env locally)."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# --- Gemini ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")

# --- Free-tier protection ---
SECONDS_BETWEEN_CALLS = float(os.getenv("SECONDS_BETWEEN_CALLS", "6"))  # 6s = max 10 requests/minute
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "4"))
DAILY_CALL_LIMIT = int(os.getenv("DAILY_CALL_LIMIT", "200"))
CACHE_DIR = os.getenv("CACHE_DIR", str(PROJECT_ROOT / ".cache"))

# --- Analysis limits ---
MAX_FINDINGS = int(os.getenv("MAX_FINDINGS", "8"))          # only the top N findings go to the AI
MAX_FIX_ATTEMPTS = int(os.getenv("MAX_FIX_ATTEMPTS", "3"))
MAX_LINES_FOR_REVIEW = 400                                  # bigger files skip the AI logic review
SEMGREP_RULES = os.getenv("SEMGREP_RULES", str(PROJECT_ROOT / "rules" / "python.yml"))

# --- Observability (optional) ---
LANGFUSE_ENABLED = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1")   # bump this when you change a prompt

# --- API security ---
API_KEY = os.getenv("API_KEY", "")
MAX_CODE_CHARS = 100_000
REQUESTS_PER_MINUTE = int(os.getenv("REQUESTS_PER_MINUTE", "5"))

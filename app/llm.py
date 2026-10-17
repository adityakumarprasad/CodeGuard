"""The ONLY place that talks to Gemini. Protects the free tier with:
cache -> daily limit -> pacing -> retry with exponential backoff."""
import hashlib
import logging
import os
import threading
import time
from datetime import date

from openai import APIConnectionError, InternalServerError, OpenAI, RateLimitError

from app import config

log = logging.getLogger(__name__)

client = OpenAI(
    api_key=config.GEMINI_API_KEY or "not-set",   # the SDK refuses an empty key; calls fail clearly with 401
    base_url=config.GEMINI_BASE_URL,
    max_retries=0,   # we do retries ourselves below, so the logic is visible and explainable
    timeout=90,
)

# Simple counters. They show up in the CLI output and evaluation report.
stats = {"api_calls": 0, "cache_hits": 0, "retries": 0}

_lock = threading.Lock()          # makes pacing work even when the API serves 2 requests at once
_last_call_time = 0.0
_today = {"date": "", "count": 0}


class DailyLimitReached(Exception):
    pass


def _cache_file(prompt: str) -> str:
    key = hashlib.sha256((config.LLM_MODEL + prompt).encode()).hexdigest()
    return os.path.join(config.CACHE_DIR, key + ".txt")


def _check_daily_limit():
    today = date.today().isoformat()
    if _today["date"] != today:            # new day: reset the counter
        _today["date"] = today
        _today["count"] = 0
    if _today["count"] >= config.DAILY_CALL_LIMIT:
        raise DailyLimitReached("Daily LLM call limit reached. Try again tomorrow.")
    _today["count"] += 1


def _wait_for_turn():
    """Pacing: at least SECONDS_BETWEEN_CALLS between two requests."""
    global _last_call_time
    with _lock:
        wait = config.SECONDS_BETWEEN_CALLS - (time.time() - _last_call_time)
        if wait > 0:
            time.sleep(wait)
        _last_call_time = time.time()


def _call_gemini(prompt: str, max_tokens: int) -> str:
    stats["api_calls"] += 1
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0,   # same input -> (almost) same output; good for security and caching
    )
    text = response.choices[0].message.content or ""
    if not text.strip():
        raise ValueError("Empty answer from the model (try a larger max_tokens)")
    return text


def ask(prompt: str, max_tokens: int = 4000) -> str:
    """Send one prompt, get text back. Safe to call on the free tier."""
    cache_file = _cache_file(prompt)
    if os.path.exists(cache_file):
        stats["cache_hits"] += 1
        with open(cache_file, encoding="utf-8") as f:
            return f.read()

    last_error = None
    for attempt in range(config.MAX_RETRIES + 1):
        if attempt > 0:
            wait = 10 * 2 ** (attempt - 1)       # 10s, 20s, 40s, 80s  (exponential backoff)
            stats["retries"] += 1
            log.warning("Gemini busy (%s). Waiting %ss, retry %s/%s",
                        type(last_error).__name__, wait, attempt, config.MAX_RETRIES)
            time.sleep(wait)

        _check_daily_limit()
        _wait_for_turn()
        try:
            text = _call_gemini(prompt, max_tokens)
        except RateLimitError as e:              # HTTP 429
            if "PerDay" in str(e):               # daily quota is gone: retrying is pointless
                _today["count"] = config.DAILY_CALL_LIMIT
                raise DailyLimitReached("Gemini free daily quota is used up.") from e
            last_error = e
            continue
        except (APIConnectionError, InternalServerError) as e:   # network problem or Google overloaded (5xx)
            last_error = e
            continue

        os.makedirs(config.CACHE_DIR, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(text)
        return text

    raise last_error

"""The ONLY place that talks to Gemini."""
import logging
import threading
import time

from openai import APIConnectionError, InternalServerError, OpenAI, RateLimitError

from app import config

log = logging.getLogger(__name__)

client = OpenAI(
    api_key=config.GEMINI_API_KEY or "not-set",   # the SDK refuses an empty key; calls fail clearly with 401
    base_url=config.GEMINI_BASE_URL,
    max_retries=0,   # we do retries ourselves, so the logic is visible and explainable
    timeout=90,
)

# Simple counters. They show up in the CLI output and evaluation report.
stats = {"api_calls": 0, "cache_hits": 0, "retries": 0}

_lock = threading.Lock()          # makes pacing work even when the API serves 2 requests at once
_last_call_time = 0.0


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
    """Send one prompt, get text back."""
    last_error = None
    for attempt in range(config.MAX_RETRIES + 1):
        if attempt > 0:
            wait = 10 * 2 ** (attempt - 1)       # 10s, 20s, 40s, 80s  (exponential backoff)
            stats["retries"] += 1
            log.warning("Gemini busy (%s). Waiting %ss, retry %s/%s",
                        type(last_error).__name__, wait, attempt, config.MAX_RETRIES)
            time.sleep(wait)

        _wait_for_turn()
        try:
            return _call_gemini(prompt, max_tokens)
        except RateLimitError as e:              # HTTP 429
            last_error = e
        except (APIConnectionError, InternalServerError) as e:   # network problem or Google overloaded (5xx)
            last_error = e

    raise last_error

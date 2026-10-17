"""The ONLY place that talks to Gemini."""
import logging

from openai import OpenAI

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
    return _call_gemini(prompt, max_tokens)

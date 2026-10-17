import pytest

from app import config, llm
from app.llm import parse_json


def test_parse_json_with_code_fence():
    assert parse_json('```json\n{"is_real": true}\n```') == {"is_real": True}


def test_parse_json_list_with_text_around():
    assert parse_json("Here you go: [] Hope it helps") == []


class FakeRateLimit(Exception):
    """Stands in for openai.RateLimitError, which is hard to build by hand."""


@pytest.fixture
def fake_gemini(monkeypatch, tmp_path):
    """No real API calls, no waiting, empty cache, fresh daily counter."""
    monkeypatch.setattr(llm, "RateLimitError", FakeRateLimit)
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(config, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(config, "SECONDS_BETWEEN_CALLS", 0)
    monkeypatch.setattr(llm, "_today", {"date": "", "count": 0})


def test_retries_after_rate_limit(fake_gemini, monkeypatch):
    replies = [FakeRateLimit("429 Too Many Requests"), "hello"]

    def fake_call(prompt, max_tokens):
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(llm, "_call_gemini", fake_call)
    assert llm.ask("hi") == "hello"


def test_daily_quota_error_stops_immediately(fake_gemini, monkeypatch):
    calls = []

    def fake_call(prompt, max_tokens):
        calls.append(prompt)
        raise FakeRateLimit("429 quota exceeded: GenerateRequestsPerDayPerProjectPerModel-FreeTier")

    monkeypatch.setattr(llm, "_call_gemini", fake_call)
    with pytest.raises(llm.DailyLimitReached):
        llm.ask("hi")
    assert len(calls) == 1          # no pointless retries


def test_second_identical_prompt_uses_cache(fake_gemini, monkeypatch):
    monkeypatch.setattr(llm, "_call_gemini", lambda prompt, max_tokens: "answer")
    llm.ask("same prompt")
    monkeypatch.setattr(llm, "_call_gemini", lambda prompt, max_tokens: pytest.fail("API called again"))
    assert llm.ask("same prompt") == "answer"

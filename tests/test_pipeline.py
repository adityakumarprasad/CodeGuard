import shutil

import pytest

from app import review, triage
from app.pipeline import analyze

VULNERABLE = """from flask import request


def calc():
    return eval(request.args.get("expr"))
"""


@pytest.mark.skipif(shutil.which("semgrep") is None, reason="semgrep not installed")
def test_findings_are_kept_when_ai_fails(monkeypatch):
    def broken_ai(*args, **kwargs):
        raise RuntimeError("Gemini is down")

    monkeypatch.setattr(triage, "triage", broken_ai)
    monkeypatch.setattr(review, "review_logic", broken_ai)

    result = analyze(VULNERABLE)
    assert result["findings"], "Semgrep should still report the eval"
    assert all(f.is_real for f in result["findings"])          # nothing hidden
    assert "unavailable" in result["findings"][0].explanation
    assert result["logic_issues"] == []

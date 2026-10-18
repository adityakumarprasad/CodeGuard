import shutil

import pytest

from app import fixer, review, triage
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


COMMAND_INJECTION = """import os
from flask import request


def ping():
    host = request.args.get("host", "")
    os.system("ping -c 1 " + host)
"""


@pytest.mark.skipif(shutil.which("semgrep") is None, reason="semgrep not installed")
def test_same_bug_flagged_by_several_rules_is_fixed_once(monkeypatch):
    fix_calls = []

    def fake_fix(finding, lines, findings_before):
        fix_calls.append(finding.line)
        return {"status": "verified", "attempts": 1, "diff": "..."}

    monkeypatch.setattr(triage, "triage", lambda finding, lines: finding)   # keep all as real
    monkeypatch.setattr(review, "review_logic", lambda lines: [])
    monkeypatch.setattr(fixer, "fix_finding", fake_fix)

    result = analyze(COMMAND_INJECTION, fix=True)
    assert len(result["findings"]) >= 2, "Semgrep flags os.system with several rules"
    assert len(fix_calls) == 1
    assert all(f.fix["status"] in ("verified", "covered") for f in result["findings"])

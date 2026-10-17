from app import llm
from app.models import Finding
from app.triage import triage


def make_finding():
    return Finding(rule_id="r", line=1, end_line=1, severity="ERROR", message="m")


def test_explicit_false_dismisses_finding(monkeypatch):
    monkeypatch.setattr(llm, "ask_json", lambda prompt: {"is_real": False, "severity": "low", "explanation": "constant"})
    assert triage(make_finding(), ["x = 1"]).is_real is False


def test_unclear_answer_keeps_finding(monkeypatch):
    # "false" as a string (or a missing field) is not a clear answer, so we keep the finding
    monkeypatch.setattr(llm, "ask_json", lambda prompt: {"is_real": "false"})
    finding = triage(make_finding(), ["x = 1"])
    assert finding.is_real is True
    assert finding.severity_ai == "high"     # falls back to Semgrep's ERROR severity

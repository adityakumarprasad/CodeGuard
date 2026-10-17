import shutil

import pytest

from app.models import Finding
from app.scanner import compact, get_snippet, run_semgrep


def test_get_snippet_numbers_lines():
    lines = ["a", "b", "c", "d"]
    assert get_snippet(lines, 2, context=1) == "1: a\n2: b\n3: c"


def test_compact_keeps_only_needed_fields():
    raw = {"results": [{"check_id": "x.y.rule", "start": {"line": 3}, "end": {"line": 3},
                        "extra": {"severity": "ERROR", "message": "bad", "lines": "....", "metadata": {}}}]}
    assert compact(raw) == [Finding(rule_id="x.y.rule", line=3, end_line=3, severity="ERROR", message="bad")]


def test_new_finding_is_real_by_default():
    finding = Finding(rule_id="r", line=1, end_line=1, severity="INFO", message="m")
    assert finding.is_real is True     # fail-safe default


@pytest.mark.skipif(shutil.which("semgrep") is None, reason="semgrep not installed")
def test_semgrep_finds_eval_on_user_input(tmp_path):
    # The rules are taint rules: they fire when user input (here a Flask request) reaches eval()
    bad = tmp_path / "bad.py"
    bad.write_text("from flask import request\n\n\ndef calc():\n    return eval(request.args.get('expr'))\n")
    assert any(f.line == 5 for f in run_semgrep(str(bad)))

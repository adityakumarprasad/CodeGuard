import shutil

import pytest

from app import llm
from app.fixer import apply_fix, extract_code, fix_finding, verify
from app.scanner import run_semgrep


def test_apply_fix_replaces_only_given_lines():
    assert apply_fix(["a", "b", "c", "d"], 2, 3, "B\nC") == ["a", "B", "C", "d"]


def test_apply_fix_can_change_line_count():
    assert apply_fix(["a", "b", "c"], 2, 2, "x\ny") == ["a", "x", "y", "c"]


def test_extract_code_from_markdown_block():
    assert extract_code("Sure:\n```python\nx = 1\n```\nDone") == "x = 1"


def test_extract_code_missing_block():
    assert extract_code("no code here") == ""


# --- verify() uses real Semgrep, no LLM ---
VULNERABLE = '''import sqlite3
from flask import request


def get_user():
    name = request.args.get("name")
    conn = sqlite3.connect("app.db")
    return conn.execute(f"SELECT * FROM users WHERE name = '{name}'").fetchall()
'''
FIXED = VULNERABLE.replace('''f"SELECT * FROM users WHERE name = '{name}'")''',
                           '''"SELECT * FROM users WHERE name = ?", (name,))''')

needs_semgrep = pytest.mark.skipif(shutil.which("semgrep") is None, reason="semgrep not installed")


def findings_of(code, tmp_path):
    path = tmp_path / "before.py"
    path.write_text(code)
    return run_semgrep(str(path))


@needs_semgrep
def test_verify_accepts_parameterized_query(tmp_path):
    before = findings_of(VULNERABLE, tmp_path)
    ok, reason = verify(FIXED, before[0].rule_id, before)
    assert ok, reason


@needs_semgrep
def test_verify_rejects_unchanged_code(tmp_path):
    before = findings_of(VULNERABLE, tmp_path)
    ok, reason = verify(VULNERABLE, before[0].rule_id, before)
    assert not ok and "still reports" in reason


def test_verify_rejects_syntax_error():
    ok, reason = verify("def broken(:\n", "any-rule", [])
    assert not ok and "syntax error" in reason


@needs_semgrep
def test_fix_loop_retries_with_feedback(tmp_path, monkeypatch):
    before = findings_of(VULNERABLE, tmp_path)
    finding = before[0]
    lines = VULNERABLE.splitlines()
    bad_reply = f"```python\n{VULNERABLE}```"     # 1st try: AI returns the code unchanged
    good_reply = f"```python\n{FIXED}```"         # 2nd try: AI returns the parameterized query
    prompts = []

    def fake_ask(prompt, *args, **kwargs):
        prompts.append(prompt)
        return bad_reply if len(prompts) == 1 else good_reply

    monkeypatch.setattr(llm, "ask", fake_ask)
    # Let the AI rewrite the whole (short) file so the fake replies line up
    monkeypatch.setattr("app.fixer.WINDOW", 100)

    result = fix_finding(finding, lines, before)
    assert result["status"] == "verified"
    assert result["attempts"] == 2
    assert "FAILED verification" in prompts[1]      # the failure reason was fed back

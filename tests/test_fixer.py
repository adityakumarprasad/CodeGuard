from app.fixer import apply_fix, extract_code


def test_apply_fix_replaces_only_given_lines():
    assert apply_fix(["a", "b", "c", "d"], 2, 3, "B\nC") == ["a", "B", "C", "d"]


def test_apply_fix_can_change_line_count():
    assert apply_fix(["a", "b", "c"], 2, 2, "x\ny") == ["a", "x", "y", "c"]


def test_extract_code_from_markdown_block():
    assert extract_code("Sure:\n```python\nx = 1\n```\nDone") == "x = 1"


def test_extract_code_missing_block():
    assert extract_code("no code here") == ""

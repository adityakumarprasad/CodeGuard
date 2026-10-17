from app.models import Finding
from app.report import to_markdown, to_sarif


def make_result():
    return {"filename": "demo\a.py", "logic_issues": [], "findings": [
        Finding(rule_id="r1", line=3, end_line=3, severity="ERROR", message="m", is_real=True, severity_ai="high"),
        Finding(rule_id="r2", line=9, end_line=9, severity="INFO", message="m", is_real=False, severity_ai="low"),
    ]}


def test_sarif_contains_only_real_findings():
    items = to_sarif([make_result()])["runs"][0]["results"]
    assert [i["ruleId"] for i in items] == ["r1"]
    assert items[0]["level"] == "error"


def test_sarif_uses_forward_slashes():
    item = to_sarif([make_result()])["runs"][0]["results"][0]
    assert item["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "demo/a.py"


def test_markdown_separates_real_and_dismissed():
    report = to_markdown(make_result())
    assert "[HIGH] r1 (line 3)" in report
    assert "## Dismissed as false positives" in report

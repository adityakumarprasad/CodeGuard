"""Turn analysis results into a human-readable Markdown report."""


def short_rule(rule_id: str) -> str:
    return rule_id.split(".")[-1]     # "python.lang.security.audit.eval-detected" -> "eval-detected"


def to_markdown(result: dict) -> str:
    findings = result["findings"]
    real = [f for f in findings if f.is_real]
    dismissed = [f for f in findings if not f.is_real]
    logic = result["logic_issues"]

    out = [
        f"# Security report: `{result['filename']}`",
        "",
        "| Semgrep findings | Confirmed real | Dismissed as false positive | Extra issues found by AI |",
        "|---|---|---|---|",
        f"| {len(findings)} | {len(real)} | {len(dismissed)} | {len(logic)} |",
        "",
        "## Confirmed issues",
    ]
    if not real:
        out.append("None.")
    for i, f in enumerate(real, 1):
        out.append(f"### {i}. [{f.severity_ai.upper()}] {short_rule(f.rule_id)} (line {f.line})")
        out.append(f.explanation or f.message)
        fix = f.fix
        if fix and fix["status"] == "verified":
            out.append(f"\n**Fix:** ✅ verified (syntax OK, Semgrep re-scan clean) after {fix['attempts']} attempt(s)")
            out += ["```diff", fix["diff"], "```"]
        elif fix:
            out.append(f"\n**Fix:** ⚠️ could not be verified ({fix['reason']}). Fix this manually.")
        out.append("")

    if logic:
        out.append("## Issues found by AI review (not detected by Semgrep)")
        for issue in logic:
            out.append(f"- **[{str(issue.get('severity', '?')).upper()}] {issue.get('title', '')}** "
                       f"(line {issue['line']}): {issue.get('explanation', '')}")
        out.append("")

    if dismissed:
        out.append("## Dismissed as false positives")
        for f in dismissed:
            out.append(f"- {short_rule(f.rule_id)} (line {f.line}): {f.explanation}")

    return "\n".join(out)


# --- SARIF: the standard format GitHub code scanning understands ---
LEVELS = {"critical": "error", "high": "error", "medium": "warning", "low": "note"}


def _sarif_result(rule_id: str, text: str, severity: str, filename: str, line: int) -> dict:
    return {
        "ruleId": rule_id,
        "level": LEVELS.get(str(severity), "warning"),
        "message": {"text": text},
        "locations": [{"physicalLocation": {
            "artifactLocation": {"uri": filename.replace("\\", "/")},   # SARIF wants forward slashes
            "region": {"startLine": line},
        }}],
    }


def to_sarif(results: list[dict]) -> dict:
    items = []
    for result in results:
        for f in result["findings"]:
            if f.is_real:
                items.append(_sarif_result(f.rule_id, f.explanation or f.message,
                                           f.severity_ai, result["filename"], f.line))
        for issue in result["logic_issues"]:
            items.append(_sarif_result("codeguard.ai-logic-review",
                                       f"{issue.get('title', '')}: {issue.get('explanation', '')}",
                                       issue.get("severity", "medium"), result["filename"], issue["line"]))
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [{"tool": {"driver": {"name": "CodeGuard AI", "rules": []}}, "results": items}],
    }

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

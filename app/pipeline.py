"""The core: scan -> triage -> logic review -> (optional) fix.
Used by the CLI, the web API, the MCP server and the evaluation."""
import logging
import os
import tempfile

from app import config, fixer, review, scanner, triage
from app.models import Finding

log = logging.getLogger(__name__)


def keep_without_ai(finding: Finding, reason: str):
    """Fail-safe: when the AI can't judge a finding, keep it and use Semgrep's severity."""
    finding.is_real = True
    finding.severity_ai = scanner.TO_AI_SEVERITY.get(finding.severity, "medium")
    finding.explanation = reason


def analyze(code: str, filename: str = "code.py", fix: bool = False) -> dict:
    lines = code.splitlines()

    # 1. Semgrep: free, local, no LLM. Written to a temp file, the user's file is never touched.
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "target.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        findings = scanner.run_semgrep(path)

    # 2. AI triage, top N findings only (protects the free quota)
    for i, finding in enumerate(findings):
        if i >= config.MAX_FINDINGS:
            keep_without_ai(finding, "Not analyzed by AI (limit reached); kept to be safe.")
            continue
        try:
            triage.triage(finding, lines)
        except Exception as e:   # rate limit, daily limit, bad JSON... the scan still finishes
            log.warning("Triage failed for line %s: %s", finding.line, e)
            keep_without_ai(finding, f"AI triage unavailable ({type(e).__name__}); kept to be safe.")

    # 3. AI logic review (issues Semgrep can't find)
    try:
        logic_issues = review.review_logic(lines)
    except Exception as e:
        log.warning("Logic review failed: %s", e)
        logic_issues = []

    # 4. Self-verifying fixes for confirmed findings
    if fix:
        for finding in findings[:config.MAX_FINDINGS]:
            if finding.is_real:
                try:
                    finding.fix = fixer.fix_finding(finding, lines, findings)
                except Exception as e:
                    finding.fix = {"status": "unverified", "attempts": 0, "reason": type(e).__name__}

    return {"filename": filename, "findings": findings, "logic_issues": logic_issues}


# Group all LLM calls of one scan into a single Langfuse trace (only when Langfuse is configured)
if config.LANGFUSE_ENABLED:
    from langfuse import observe
    analyze = observe(name="security-scan")(analyze)

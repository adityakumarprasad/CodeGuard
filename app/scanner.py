"""Step 1: run Semgrep and turn its long JSON output into a short list of findings."""
import json
import subprocess

from app import config
from app.models import Finding

# Semgrep has used both naming styles for severity, so we accept both.
SEVERITY_RANK = {"CRITICAL": 0, "ERROR": 1, "HIGH": 1, "WARNING": 2, "MEDIUM": 2, "INFO": 3, "LOW": 3}
TO_AI_SEVERITY = {"CRITICAL": "critical", "ERROR": "high", "HIGH": "high",
                  "WARNING": "medium", "MEDIUM": "medium", "INFO": "low", "LOW": "low"}


def run_semgrep(path: str) -> list[Finding]:
    """Scan one file. Returns findings sorted from most to least severe."""
    command = [
        "semgrep", "scan",
        "--config", config.SEMGREP_RULES,
        "--json", "--quiet",
        "--metrics=off",      # don't send usage data anywhere
        "--timeout", "30",    # max seconds per rule, so a huge file can't hang us
        path,
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=180)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"Semgrep failed: {result.stderr[:500]}")
    return compact(json.loads(result.stdout))


def compact(semgrep_output: dict) -> list[Finding]:
    """Keep only the 5 fields we need. Raw Semgrep JSON is ~10x bigger, and every
    extra character we send to the LLM costs free-tier quota."""
    findings = []
    for r in semgrep_output.get("results", []):
        findings.append(Finding(
            rule_id=r["check_id"],
            line=r["start"]["line"],
            end_line=r["end"]["line"],
            severity=r["extra"].get("severity", "INFO"),
            message=r["extra"].get("message", "")[:300],
        ))
    findings.sort(key=lambda f: SEVERITY_RANK.get(f.severity, 4))
    return findings


def number_lines(lines: list[str], start: int, end: int) -> str:
    """Return lines start..end (1-based) as '12: code' so the LLM can refer to line numbers."""
    return "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1))


def get_snippet(lines: list[str], center: int, context: int = 15) -> str:
    """Only the code around a finding (±15 lines), never the whole file."""
    start = max(1, center - context)
    end = min(len(lines), center + context)
    return number_lines(lines, start, end)

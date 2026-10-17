"""The data model: one security finding.

A dataclass instead of a plain dict:
- finding.rule_id instead of finding["rule_id"], so typos are caught by the editor
- every field is listed (and documented) in one place
- default values are the fail-safe values (a finding counts as real until the AI says otherwise)
"""
from dataclasses import dataclass


@dataclass
class Finding:
    # Filled by Semgrep (scanner.py)
    rule_id: str
    line: int
    end_line: int
    severity: str               # Semgrep's own severity, e.g. "ERROR" or "WARNING"
    message: str

    # Filled by the AI (triage.py)
    is_real: bool = True        # fail-safe default: keep the finding
    severity_ai: str = "medium"
    explanation: str = ""

    # Filled by fixer.py when --fix is used: {"status": "verified" | "unverified", "attempts": ..., ...}
    fix: dict | None = None

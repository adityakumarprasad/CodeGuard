"""Is Semgrep + AI better than Semgrep alone?

Ground truth: in evaluation/cases, every truly vulnerable line ends with a comment
'# VULN: <type>'. We remove those comments before scanning (so the AI can't see the
answers) and remember their line numbers.

Usage:
    uv run python -m evaluation.run_eval          # triage + logic review
    uv run python -m evaluation.run_eval --fix    # also measure verified fixes
"""
import argparse
import glob
import logging
import os
import sys
import time

from app import config, llm
from app.pipeline import analyze

CASES_DIR = os.path.join(os.path.dirname(__file__), "cases")
RESULTS_FILE = os.path.join(os.path.dirname(__file__), "results.md")
TOLERANCE = 2   # a finding within 2 lines of the real bug counts as a hit


def load_case(path: str) -> tuple[str, set[int]]:
    """Remove '# VULN' markers (so the AI can't see them) and return their line numbers."""
    clean_lines, truth = [], set()
    with open(path, encoding="utf-8") as f:
        for number, line in enumerate(f.read().splitlines(), start=1):
            if "# VULN" in line:
                truth.add(number)
                line = line.split("# VULN")[0].rstrip()
            clean_lines.append(line)
    return "\n".join(clean_lines) + "\n", truth


def score(predicted_lines: list[int], truth: set[int]) -> tuple[int, int, int]:
    """Returns (correct findings, wrong findings, real bugs found)."""
    correct = sum(1 for p in predicted_lines if any(abs(p - t) <= TOLERANCE for t in truth))
    wrong = len(predicted_lines) - correct
    found = sum(1 for t in truth if any(abs(p - t) <= TOLERANCE for p in predicted_lines))
    return correct, wrong, found


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f}%" if b else "n/a"


def ratio(a: int, b: int) -> float:
    return a / b if b else 0.0


def log_scores_to_langfuse(precision: float, recall: float, fix_rate: float | None):
    """Attach the evaluation numbers to this run's trace, so runs can be compared in Langfuse."""
    if not config.LANGFUSE_ENABLED:
        return
    from langfuse import get_client
    langfuse = get_client()
    tags = {"model": config.LLM_MODEL, "prompt_version": config.PROMPT_VERSION}
    langfuse.score_current_trace(name="precision", value=precision, metadata=tags)
    langfuse.score_current_trace(name="recall", value=recall, metadata=tags)
    if fix_rate is not None:
        langfuse.score_current_trace(name="fix_rate", value=fix_rate, metadata=tags)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true")
    args = parser.parse_args()

    totals = {"bugs": 0, "s_correct": 0, "s_wrong": 0, "s_found": 0,
              "a_correct": 0, "a_wrong": 0, "a_found": 0, "fix_tried": 0, "fix_ok": 0}
    rows = []
    started = time.time()

    for path in sorted(glob.glob(os.path.join(CASES_DIR, "*.py"))):
        name = os.path.basename(path)
        print(f"Evaluating {name} ...")
        code, truth = load_case(path)
        result = analyze(code, name, fix=args.fix)
        if llm.stats["quota_exhausted"]:
            # Without the AI, "Semgrep + AI" silently becomes "Semgrep alone": refuse to report fake numbers.
            # Answers so far are cached, so re-running after the quota resets continues from here for free.
            print(f"\nSTOPPED at {name}: the LLM daily quota is used up. No results written. "
                  f"Re-run after the quota resets; cached answers make it resume where it stopped.")
            sys.exit(1)

        semgrep_lines = [f.line for f in result["findings"]]
        ai_lines = ([f.line for f in result["findings"] if f.is_real]
                    + [i["line"] for i in result["logic_issues"]])
        s_correct, s_wrong, s_found = score(semgrep_lines, truth)
        a_correct, a_wrong, a_found = score(ai_lines, truth)
        fixes = [f.fix for f in result["findings"] if f.fix and f.fix["status"] != "covered"]
        fix_ok = sum(1 for fx in fixes if fx["status"] == "verified")

        for key, value in [("bugs", len(truth)), ("s_correct", s_correct), ("s_wrong", s_wrong),
                           ("s_found", s_found), ("a_correct", a_correct), ("a_wrong", a_wrong),
                           ("a_found", a_found), ("fix_tried", len(fixes)), ("fix_ok", fix_ok)]:
            totals[key] += value
        rows.append(f"| {name} | {len(truth)} | {s_found} / {s_wrong} | {a_found} / {a_wrong} | "
                    f"{f'{fix_ok}/{len(fixes)}' if args.fix else '-'} |")

    t = totals
    report = [
        "# Evaluation results", "",
        f"Model: `{config.LLM_MODEL}` · cases: {len(rows)} · time: {time.time() - started:.0f}s · "
        f"LLM usage: {llm.stats}", "",
        "| Metric | Semgrep alone | Semgrep + AI |", "|---|---|---|",
        f"| Precision (findings that are real) | {pct(t['s_correct'], t['s_correct'] + t['s_wrong'])} "
        f"| {pct(t['a_correct'], t['a_correct'] + t['a_wrong'])} |",
        f"| Recall (real bugs found) | {pct(t['s_found'], t['bugs'])} | {pct(t['a_found'], t['bugs'])} |",
        f"| False alarms | {t['s_wrong']} | {t['a_wrong']} |",
    ]
    if args.fix:
        report.append(f"| Fixes verified | - | {t['fix_ok']}/{t['fix_tried']} ({pct(t['fix_ok'], t['fix_tried'])}) |")
    report += ["", "## Per case (real bugs found / false alarms)", "",
               "| Case | Real bugs | Semgrep | Semgrep + AI | Fixes verified |", "|---|---|---|---|---|", *rows]

    text = "\n".join(report)
    print("\n" + text)
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        f.write(text + "\n")

    log_scores_to_langfuse(
        precision=ratio(t["a_correct"], t["a_correct"] + t["a_wrong"]),
        recall=ratio(t["a_found"], t["bugs"]),
        fix_rate=ratio(t["fix_ok"], t["fix_tried"]) if args.fix else None,
    )
    llm.flush()


# The whole evaluation becomes one trace, with each scan nested inside it
if config.LANGFUSE_ENABLED:
    from langfuse import observe
    main = observe(name="evaluation-run")(main)


if __name__ == "__main__":
    main()

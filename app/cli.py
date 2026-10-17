"""Command line:  uv run python -m app.cli FILE [FILE ...] [--fix] [--sarif out.sarif]"""
import argparse
import logging
import sys

from app import llm
from app.pipeline import analyze
from app.report import to_markdown


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.stdout.reconfigure(encoding="utf-8")   # Windows terminals default to cp1252, which can't print ✅
    parser = argparse.ArgumentParser(description="CodeGuard AI: security review for Python files")
    parser.add_argument("files", nargs="+")
    parser.add_argument("--fix", action="store_true", help="generate and verify fixes")
    parser.add_argument("--sarif", help="also write a SARIF file (GitHub code scanning)")
    args = parser.parse_args()

    results = []
    for path in args.files:
        with open(path, encoding="utf-8") as f:
            result = analyze(f.read(), filename=path, fix=args.fix)
        results.append(result)
        print(to_markdown(result))

    print(f"\nLLM usage: {llm.stats}")


if __name__ == "__main__":
    main()

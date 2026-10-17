"""MCP server: lets AI coding tools (Claude Code, Cursor, ...) call CodeGuard as a tool.
IMPORTANT: MCP talks over stdout, so never print() here. Logs go to stderr."""
import logging
import sys

from mcp.server import MCPServer   # called FastMCP in mcp 1.x

from app import config, llm
from app.pipeline import analyze
from app.report import to_markdown

logging.basicConfig(stream=sys.stderr, level=logging.INFO)

mcp = MCPServer("codeguard")


@mcp.tool()
def security_review(file_path: str, fix: bool = False) -> str:
    """Scan a Python file for security vulnerabilities. Semgrep finds candidates, AI removes
    false positives and finds logic flaws. With fix=True, also returns fixes verified by a Semgrep re-scan.

    Args:
        file_path: absolute path to a .py file
        fix: also generate verified fixes (slower)
    """
    if not file_path.endswith(".py"):
        return "Only Python (.py) files are supported."
    with open(file_path, encoding="utf-8") as f:
        code = f.read()
    if len(code) > config.MAX_CODE_CHARS:
        return "File is too large to scan."
    report = to_markdown(analyze(code, file_path, fix=fix))
    llm.flush()
    return report


if __name__ == "__main__":
    mcp.run()   # stdio transport

import asyncio

from app.mcp_server import mcp, security_review


def test_security_review_tool_is_registered():
    tools = asyncio.run(mcp.list_tools())
    assert [t.name for t in tools] == ["security_review"]


def test_non_python_files_are_rejected():
    assert security_review("notes.txt") == "Only Python (.py) files are supported."

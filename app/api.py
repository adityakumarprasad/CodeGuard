"""Web API + a tiny web page."""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import config
from app.pipeline import analyze
from app.report import to_markdown

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="CodeGuard AI")
STATIC_DIR = Path(__file__).parent / "static"


class ScanRequest(BaseModel):
    code: str = Field(min_length=1, max_length=config.MAX_CODE_CHARS)   # input size limit
    filename: str = Field(default="code.py", max_length=100)
    fix: bool = False


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/scan")
def scan(req: ScanRequest):
    result = analyze(req.code, req.filename, fix=req.fix)
    # FastAPI turns dataclasses (our Finding objects) into JSON automatically
    return {"report_markdown": to_markdown(result), "result": result}

"""Web API + a tiny web page.
Hardening: API key, per-IP rate limit, input size limits, no user code is ever executed."""
import logging
import secrets
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import config
from app.pipeline import analyze
from app.report import to_markdown

logging.basicConfig(level=logging.INFO)
if not config.API_KEY:
    logging.warning("API_KEY is not set: the API is open. OK for local development only!")

app = FastAPI(title="CodeGuard AI")
STATIC_DIR = Path(__file__).parent / "static"


class ScanRequest(BaseModel):
    code: str = Field(min_length=1, max_length=config.MAX_CODE_CHARS)   # input size limit
    filename: str = Field(default="code.py", max_length=100)
    fix: bool = False


def require_api_key(x_api_key: str = Header(default="")):
    if not config.API_KEY:
        return
    # compare_digest takes the same time for right and wrong keys (prevents timing attacks)
    if not secrets.compare_digest(x_api_key.encode(), config.API_KEY.encode()):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


recent_requests: dict[str, list[float]] = {}   # ip -> times of requests in the last minute


def rate_limit(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    recent = [t for t in recent_requests.get(ip, []) if now - t < 60]
    if len(recent) >= config.REQUESTS_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Too many scans. Please wait a minute.")
    recent.append(now)
    recent_requests[ip] = recent


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/scan", dependencies=[Depends(require_api_key), Depends(rate_limit)])
def scan(req: ScanRequest):
    result = analyze(req.code, req.filename, fix=req.fix)
    # FastAPI turns dataclasses (our Finding objects) into JSON automatically
    return {"report_markdown": to_markdown(result), "result": result}

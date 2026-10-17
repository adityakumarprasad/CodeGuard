from fastapi.testclient import TestClient

from app import api, config
from app.models import Finding

client = TestClient(api.app)


def fake_analyze(code, filename, fix=False):
    return {"filename": filename, "findings": [Finding("r", 1, 1, "ERROR", "m")], "logic_issues": []}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_home_page_is_served():
    assert "CodeGuard AI" in client.get("/").text


def test_scan_rejects_missing_api_key(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "secret")
    assert client.post("/scan", json={"code": "x = 1"}).status_code == 401


def test_scan_rejects_empty_code(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "")
    assert client.post("/scan", json={"code": ""}).status_code == 422


def test_scan_returns_report_with_valid_key(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "secret")
    monkeypatch.setattr(api, "analyze", fake_analyze)
    monkeypatch.setattr(api, "recent_requests", {})
    response = client.post("/scan", json={"code": "x = 1"}, headers={"X-API-Key": "secret"})
    assert response.status_code == 200
    assert response.json()["result"]["findings"][0]["rule_id"] == "r"


def test_rate_limit_blocks_too_many_scans(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "")
    monkeypatch.setattr(config, "REQUESTS_PER_MINUTE", 2)
    monkeypatch.setattr(api, "analyze", fake_analyze)
    monkeypatch.setattr(api, "recent_requests", {})
    codes = [client.post("/scan", json={"code": "x = 1"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]

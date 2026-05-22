from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_index_renders():
    response = client.get("/")
    assert response.status_code == 200
    assert "Content Writer AI" in response.text


def test_health_reports_key_status():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "has_api_key" in body


def test_analyze_requires_title():
    response = client.post("/analyze-and-write", data={
        "page_title": "", "primary_keywords": "x",
    })
    assert response.status_code == 200
    assert "required" in response.text.lower() or "error" in response.text.lower()

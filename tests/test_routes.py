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


def test_analyze_renders_full_article(monkeypatch):
    """The whole generated article must render, not just the intro.

    Regression test for the bug where the model abbreviated the article
    because it was one field of a large JSON. The article now comes from its
    own dedicated call, so every section must appear in the response.
    """
    long_article = "# Web Frameworks Guide\n\n" + "\n\n".join(
        f"## Section {i}\n\nThis is paragraph {i} with real explanatory content."
        for i in range(1, 11)
    )
    analysis_json = (
        '{"competitors": [], "gaps": [], '
        '"seo": {"title": "T", "slug": "s", "metaDescription": "m", '
        '"googleNewsHeading": "g", "uniqueAngleAdded": "u"}, '
        '"flaggedSentences": [], "auditRecommendations": []}'
    )

    def fake_generate(prompt, json_mode=False, temperature=None, max_tokens=None):
        if json_mode:
            return analysis_json
        if "Write" in prompt and "HARD REQUIREMENT" in prompt:
            return long_article
        return "competitive summary"

    monkeypatch.setattr("app.main.safe_generate", fake_generate)
    monkeypatch.setattr("app.config.GROQ_API_KEY", "test-key")

    response = client.post("/analyze-and-write", data={
        "page_title": "Web Frameworks", "primary_keywords": "web frameworks",
        "target_word_count": "1500",
    })
    assert response.status_code == 200
    # The end of the article must be present, proving nothing was truncated.
    assert "Section 10" in response.text
    assert "paragraph 10" in response.text

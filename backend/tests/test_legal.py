from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_terms_page_renders():
    response = client.get("/terms")

    assert response.status_code == 200
    assert "Условия использования" in response.text


def test_privacy_page_renders():
    response = client.get("/privacy")

    assert response.status_code == 200
    assert "Политика конфиденциальности" in response.text


def test_privacy_page_discloses_third_party_processors():
    response = client.get("/privacy")

    for processor in ["OpenAI", "Firecrawl", "Google", "Supabase", "Railway", "Telegram"]:
        assert processor in response.text

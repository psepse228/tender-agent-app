from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_security_headers_present_on_every_response():
    response = client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_no_frame_options_header_since_this_must_stay_embeddable_in_telegram():
    response = client.get("/health")

    assert "x-frame-options" not in response.headers

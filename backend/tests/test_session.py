import time

from app.auth.session import create_session_token, verify_session_token

SECRET = "test-session-secret"


def test_round_trips_a_valid_token():
    payload = {"email": "owner@example.com", "tenantId": "t-1", "exp": time.time() + 3600}

    token = create_session_token(payload, SECRET)
    result = verify_session_token(token, SECRET)

    assert result["email"] == "owner@example.com"
    assert result["tenantId"] == "t-1"


def test_rejects_token_signed_with_a_different_secret():
    token = create_session_token({"email": "a@b.com", "tenantId": "t-1", "exp": time.time() + 3600}, SECRET)

    assert verify_session_token(token, "wrong-secret") is None


def test_rejects_expired_token():
    token = create_session_token({"email": "a@b.com", "tenantId": "t-1", "exp": time.time() - 10}, SECRET)

    assert verify_session_token(token, SECRET) is None


def test_rejects_malformed_token_without_a_dot():
    assert verify_session_token("not-a-real-token", SECRET) is None


def test_rejects_tampered_payload():
    token = create_session_token({"email": "a@b.com", "tenantId": "t-1", "exp": time.time() + 3600}, SECRET)
    encoded, signature = token.split(".", 1)
    tampered = encoded + "x." + signature

    assert verify_session_token(tampered, SECRET) is None


def test_rejects_payload_missing_required_fields():
    token = create_session_token({"email": "a@b.com", "exp": time.time() + 3600}, SECRET)

    assert verify_session_token(token, SECRET) is None

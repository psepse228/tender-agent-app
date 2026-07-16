"""Signed session tokens for the Google-login flow, stored in an HttpOnly
cookie.

Format: base64url(JSON payload) + "." + hex(HMAC_SHA256(payload, secret)).
Same scheme as Cortège's dashboard session token, ported to Python so both
products' web-login sessions work the same way.
"""

import base64
import hashlib
import hmac
import json
import time


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded)


def _sign(encoded_payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), encoded_payload.encode(), hashlib.sha256).hexdigest()


def create_session_token(payload: dict, secret: str) -> str:
    encoded = _b64url_encode(json.dumps(payload).encode())
    return f"{encoded}.{_sign(encoded, secret)}"


def verify_session_token(token: str, secret: str) -> dict | None:
    try:
        encoded, signature = token.split(".", 1)
    except ValueError:
        return None

    expected = _sign(encoded, secret)
    if not hmac.compare_digest(signature, expected):
        return None

    try:
        payload = json.loads(_b64url_decode(encoded))
    except (ValueError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    if not isinstance(payload.get("exp"), (int, float)) or payload["exp"] < time.time():
        return None
    if not isinstance(payload.get("email"), str) or not isinstance(payload.get("tenantId"), str):
        return None
    return payload

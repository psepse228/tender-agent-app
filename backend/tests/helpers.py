"""Test-only helpers. Independently re-implements Telegram's initData
signing spec so tests can produce validly-signed payloads without
depending on app.auth.telegram (which is the thing under test)."""
import hashlib
import hmac
import time
from urllib.parse import urlencode

from app.auth.session import create_session_token


def sign_init_data(fields: dict[str, str], bot_token: str) -> str:
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(fields.items())
    )
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return urlencode({**fields, "hash": computed_hash})


def session_cookie(tenant_id: str, secret: str, email: str = "owner@example.com") -> str:
    """A valid tender_agent_session cookie value for the given tenant --
    Google login is the only auth path now, so every router test authenticates
    this way instead of the old Telegram tma header."""
    return create_session_token(
        {"email": email, "tenantId": tenant_id, "exp": time.time() + 3600}, secret
    )

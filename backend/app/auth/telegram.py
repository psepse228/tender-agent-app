import hashlib
import hmac
import time
from urllib.parse import parse_qsl

MAX_AUTH_AGE_SECONDS = 24 * 60 * 60


class InitDataError(Exception):
    pass


def validate_init_data(init_data: str, bot_token: str) -> dict[str, str]:
    """Validate a Telegram Mini App initData string against bot_token.

    Returns the parsed key-value pairs (hash removed) on success.
    Raises InitDataError on malformed input, missing/invalid hash, or a
    stale/invalid auth_date (more than 24h old, or non-numeric).
    """
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError as exc:
        raise InitDataError("malformed init_data") from exc

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InitDataError("missing hash field")

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(pairs.items())
    )

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise InitDataError("invalid hash")

    try:
        auth_date = int(pairs.get("auth_date", 0))
    except ValueError as exc:
        raise InitDataError("invalid auth_date") from exc
    if time.time() - auth_date > MAX_AUTH_AGE_SECONDS:
        raise InitDataError("stale auth_date")

    return pairs

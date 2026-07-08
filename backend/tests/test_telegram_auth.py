import time

import pytest

from app.auth.telegram import InitDataError, validate_init_data
from tests.helpers import sign_init_data

BOT_TOKEN = "123456:TEST-fake-token-for-tests"


def test_accepts_correctly_signed_payload():
    fields = {
        "user": '{"id":111,"first_name":"Test"}',
        "auth_date": str(int(time.time())),
        "query_id": "AAH_test",
    }
    init_data = sign_init_data(fields, BOT_TOKEN)

    result = validate_init_data(init_data, BOT_TOKEN)

    assert result["auth_date"] == fields["auth_date"]
    assert result["user"] == fields["user"]


def test_rejects_payload_signed_with_a_different_token():
    fields = {"user": '{"id":111}', "auth_date": str(int(time.time()))}
    init_data = sign_init_data(fields, "999:a-different-bot-token")

    with pytest.raises(InitDataError, match="invalid hash"):
        validate_init_data(init_data, BOT_TOKEN)


def test_rejects_tampered_field():
    fields = {"user": '{"id":111}', "auth_date": str(int(time.time()))}
    init_data = sign_init_data(fields, BOT_TOKEN)
    tampered = init_data.replace("id%22%3A111", "id%22%3A999")

    with pytest.raises(InitDataError, match="invalid hash"):
        validate_init_data(tampered, BOT_TOKEN)


def test_rejects_stale_auth_date():
    stale_time = int(time.time()) - (25 * 60 * 60)
    fields = {"user": '{"id":111}', "auth_date": str(stale_time)}
    init_data = sign_init_data(fields, BOT_TOKEN)

    with pytest.raises(InitDataError, match="stale"):
        validate_init_data(init_data, BOT_TOKEN)


def test_rejects_missing_hash():
    with pytest.raises(InitDataError, match="missing hash"):
        validate_init_data("user=%7B%22id%22%3A111%7D&auth_date=123", BOT_TOKEN)


def test_rejects_malformed_init_data():
    with pytest.raises(InitDataError, match="malformed"):
        validate_init_data("foobar", BOT_TOKEN)


def test_rejects_non_numeric_auth_date():
    fields = {"user": '{"id":111}', "auth_date": "not-a-number"}
    init_data = sign_init_data(fields, BOT_TOKEN)

    with pytest.raises(InitDataError, match="invalid auth_date"):
        validate_init_data(init_data, BOT_TOKEN)

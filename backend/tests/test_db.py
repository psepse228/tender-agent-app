from unittest.mock import MagicMock

from app import db


def test_get_supabase_client_uses_settings(monkeypatch):
    db.get_supabase_client.cache_clear()
    create_client_mock = MagicMock(return_value="fake-client")
    monkeypatch.setattr(db, "create_client", create_client_mock)

    try:
        client = db.get_supabase_client()

        assert client == "fake-client"
        create_client_mock.assert_called_once_with(
            "https://example.supabase.co", "test-service-role-key"
        )
    finally:
        db.get_supabase_client.cache_clear()

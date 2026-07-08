from app.config import Settings


def test_settings_reads_from_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://tenant.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "secret-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-real")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "999:real-token")

    settings = Settings()

    assert settings.supabase_url == "https://tenant.supabase.co"
    assert settings.supabase_key == "secret-key"
    assert settings.telegram_bot_token == "999:real-token"


def test_settings_requires_all_credentials(monkeypatch):
    for var in ("SUPABASE_URL", "SUPABASE_KEY", "OPENAI_API_KEY", "FIRECRAWL_API_KEY", "TELEGRAM_BOT_TOKEN"):
        monkeypatch.delenv(var, raising=False)

    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None)

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_key: str
    openai_api_key: str
    firecrawl_api_key: str
    telegram_bot_token: str
    environment: str = "development"

    # Google OAuth self-serve web login -- all optional so existing
    # Telegram-only deployments keep working without configuring these.
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_redirect_uri: str | None = None
    session_secret: str | None = None
    dev_bypass_email: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    llm_model: str = "gemini/gemini-3.5-flash-lite"

    telegram_bot_token: str = ""  # from @BotFather
    channel: str = "telegram"  # "telegram" | "console" (prints instead of sending)

    database_url: str = "sqlite:///./hermod.db"
    timezone: str = "Australia/Sydney"
    n8n_alert_webhook_url: str = ""

    # Dashboard API. If API_KEY is set, every /api request needs header "X-API-Key: <key>".
    api_key: str = ""
    # Comma-separated browser origins allowed to call the API (the React dev server).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    llm_model: str = "gemini/gemini-2.5-flash"

    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_graph_version: str = "v21.0"
    whatsapp_checkin_template: str = "hello_world"

    database_url: str = "sqlite:///./hermod.db"
    timezone: str = "Australia/Sydney"
    n8n_alert_webhook_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()

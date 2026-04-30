from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Pharmacy Intelligence Assistant"
    pharmacy_name: str = "PharMareen"
    app_version: str = "day-2"
    timezone: str = "Africa/Nairobi"
    public_base_url: str | None = Field(default=None, validation_alias=AliasChoices("APP_BASE_URL", "PUBLIC_BASE_URL"))

    openai_api_key: str = ""
    openai_parse_model: str = "gpt-5"
    openai_transcription_model: str = "whisper-1"
    enable_voice_input: bool = True

    google_sheets_spreadsheet_id: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_SHEET_ID", "GOOGLE_SHEETS_SPREADSHEET_ID"),
    )
    google_service_account_json: str = Field(
        default="./service-account.json",
        validation_alias=AliasChoices("GOOGLE_SHEETS_CREDENTIALS", "GOOGLE_SERVICE_ACCOUNT_JSON"),
    )

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = Field(
        default="",
        validation_alias=AliasChoices("TWILIO_WHATSAPP_NUMBER", "TWILIO_WHATSAPP_FROM"),
    )
    owner_whatsapp_to: str = ""
    validate_twilio_signature: bool = True

    report_trigger_token: str | None = None
    report_storage_mode: str = "local"
    report_public_dir: str = "reports_pdf"
    support_contact: str = "Support contact coming soon"


@lru_cache
def get_settings() -> Settings:
    return Settings()

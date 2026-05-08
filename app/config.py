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
    app_version: str = "whatsapp-web-mvp"
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
    pharmareen_admin_sheet_id: str = Field(
        default="",
        validation_alias=AliasChoices("PHARMAREEN_ADMIN_SHEET_ID", "ADMIN_SHEET_ID"),
    )
    pharmareen_default_pharmacy_id: str = Field(
        default="",
        validation_alias=AliasChoices("PHARMAREEN_DEFAULT_PHARMACY_ID", "DEFAULT_PHARMACY_ID"),
    )

    whatsapp_provider: str = "whatsapp_web"
    whatsapp_number: str = Field(
        default="",
        validation_alias=AliasChoices("WHATSAPP_NUMBER", "WHATSAPP_WEB_NUMBER"),
    )
    allowed_whatsapp_numbers: str = Field(
        default="",
        validation_alias=AliasChoices("ALLOWED_WHATSAPP_NUMBERS", "ALLOWED_PHONE_NUMBERS"),
    )
    allow_all_direct_chats_for_test: bool = Field(
        default=False,
        validation_alias=AliasChoices("ALLOW_ALL_DIRECT_CHATS_FOR_TEST", "ALLOW_ALL_DIRECT_CHATS"),
    )
    owner_whatsapp_to: str = ""
    demo_mode: bool = False

    report_trigger_token: str | None = None
    report_storage_mode: str = "local"
    report_public_dir: str = "reports_pdf"
    support_contact: str = "Support contact coming soon"

    meta_verify_token: str = ""
    meta_access_token: str = ""
    meta_phone_number_id: str = ""
    meta_waba_id: str = Field(default="", validation_alias=AliasChoices("META_WHATSAPP_BUSINESS_ACCOUNT_ID", "META_WABA_ID"))
    meta_graph_api_version: str = "v21.0"

    def __init__(self, **data):
        local_test_mode = data.get("_env_file", object()) is None
        owner_was_explicit = "owner_whatsapp_to" in data or "OWNER_WHATSAPP_TO" in data
        if local_test_mode and not owner_was_explicit:
            data["owner_whatsapp_to"] = ""
        super().__init__(**data)


@lru_cache
def get_settings() -> Settings:
    return Settings()

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str
    openai_model: str = "gpt-6-astra"

    google_oauth_client_secret_file: str = "secrets/google_client_secret.json"
    google_oauth_token_file: str = "secrets/google_token.json"
    gmail_query: str = 'is:unread has:attachment subject:"[グルメCanva]" -label:grume/done -label:grume/processing'
    gmail_processing_label: str = "grume/processing"
    gmail_done_label: str = "grume/done"
    gmail_error_label: str = "grume/error"

    canva_api_base: str = "https://api.canva.com/rest/v1"
    canva_client_id: str | None = None
    canva_client_secret: str | None = None
    canva_redirect_uri: str = "http://127.0.0.1:8765/callback"
    canva_token_file: str = "secrets/canva_token.json"
    canva_source_type: Literal["design", "brand_template"] = "design"
    canva_source_id: str | None = None

    output_dir: str = "output"
    default_area: str = "大阪"
    min_images: int = 1
    max_images: int = 20
    poll_interval_seconds: int = 60
    log_level: str = "INFO"

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)

    @property
    def canva_token_path(self) -> Path:
        return Path(self.canva_token_file)

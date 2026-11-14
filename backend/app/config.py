"""App settings from .env (pydantic-settings). No hardcoded keys or model names."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# repo root = parent of backend/
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_path(value: Path | str) -> Path:
    """Absolute paths stay; relative paths are anchored at the repo root."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = _REPO_ROOT / path
    return path.resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLMs — default extract = local Ollama llama3.2 (no cloud key)
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    extract_provider: str = "ollama"  # ollama | gemini | anthropic
    extract_model: str = "llama3.2"
    ollama_base_url: str = "http://127.0.0.1:11434"
    draft_provider: str = "ollama"
    draft_model: str = "llama3.2"
    llm_timeout_s: int = 120
    max_pages_per_doc: int = 4
    demo_offline: bool = False
    prompt_version: str = "3"

    # Prices USD / 1M tokens
    price_gemini_3_8_flash_in: float = 0.75
    price_gemini_3_8_flash_out: float = 3.75
    price_claude_sonnet_5_5_in: float = 2.00
    price_claude_sonnet_5_5_out: float = 10.00
    price_claude_haiku_5_5_in: float = 0.10
    price_claude_haiku_5_5_out: float = 0.50

    # Human cost baseline
    officer_hourly_usd: float = 5.00
    officer_minutes_per_file: int = 45

    # App
    data_dir: Path = Field(default=_REPO_ROOT / "data")
    database_url: str = "sqlite:///./data/visaref.db"
    retention_days_after_decision: int = 7
    retention_days_idle: int = 30
    file_encryption_key: str = ""
    officer_name: str = "Gloria"
    officer_pin: str = ""
    session_secret: str = ""
    checklist_dir: Path = Field(default=_REPO_ROOT / "checklists")
    next_public_api_url: str = "http://localhost:8000"

    # Optional channels
    email_imap_host: str = ""
    email_imap_port: int = 993
    email_imap_user: str = ""
    email_imap_password: str = ""
    email_imap_folder: str = "INBOX"
    email_subject_filter: str = "VISA"
    email_read_unread_only: bool = True
    email_poll_interval_s: int = 30
    email_connection_timeout_s: int = 20
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""
    smtp_host: str = ""
    smtp_user: str = ""
    smtp_password: str = ""

    # Observability
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    @field_validator("data_dir", "checklist_dir", mode="before")
    @classmethod
    def _absolute_dirs(cls, v: Path | str) -> Path:
        return _resolve_path(v)

    @model_validator(mode="after")
    def _sqlite_under_data_dir(self) -> Settings:
        """Keep the default SQLite file under data_dir even if CWD is backend/."""
        if self.database_url.startswith("sqlite:///./data/"):
            db_name = Path(self.database_url.removeprefix("sqlite:///./data/")).name
            self.database_url = f"sqlite:///{self.data_dir / db_name}"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

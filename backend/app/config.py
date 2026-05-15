from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    port: int
    auto_create_tables: bool
    allowed_origins: list[str]
    local_dev_user_email: str
    openai_api_key: str | None
    openai_api_base_url: str
    openai_relay_base_url: str | None
    anthropic_api_key: str | None
    anthropic_version: str
    claude_api_base_url: str
    claude_relay_base_url: str | None


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str) -> list[str]:
    raw_value = os.getenv(name, default)
    return [part.strip() for part in raw_value.split(",") if part.strip()]


def _env_optional(name: str) -> str | None:
    raw_value = os.getenv(name)
    if raw_value is None:
        return None

    value = raw_value.strip()
    return value or None


def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/convo_maker"),
        port=int(os.getenv("PORT", "3000")),
        auto_create_tables=_env_bool("AUTO_CREATE_TABLES", True),
        allowed_origins=_env_list("ALLOWED_ORIGINS", "http://localhost:3000,chrome-extension://*"),
        local_dev_user_email=os.getenv("LOCAL_DEV_USER_EMAIL", "local-dev@convo-maker.test"),
        openai_api_key=_env_optional("OPENAI_API_KEY"),
        openai_api_base_url=os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com"),
        openai_relay_base_url=_env_optional("OPENAI_RELAY_BASE_URL"),
        anthropic_api_key=_env_optional("ANTHROPIC_API_KEY"),
        anthropic_version=os.getenv("ANTHROPIC_VERSION", "2023-06-01"),
        claude_api_base_url=os.getenv("CLAUDE_API_BASE_URL", "https://api.anthropic.com"),
        claude_relay_base_url=_env_optional("CLAUDE_RELAY_BASE_URL"),
    )


settings = get_settings()

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


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str) -> list[str]:
    raw_value = os.getenv(name, default)
    return [part.strip() for part in raw_value.split(",") if part.strip()]


def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/convo_maker"),
        port=int(os.getenv("PORT", "3000")),
        auto_create_tables=_env_bool("AUTO_CREATE_TABLES", True),
        allowed_origins=_env_list("ALLOWED_ORIGINS", "http://localhost:3000,chrome-extension://*"),
        local_dev_user_email=os.getenv("LOCAL_DEV_USER_EMAIL", "local-dev@convo-maker.test"),
    )


settings = get_settings()


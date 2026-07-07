from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_env_file(path: Path = ENV_FILE) -> None:
    """Fill os.environ from a KEY=VALUE file without overriding existing vars.
    Tolerates shell-style `export KEY=value` lines; skips non-literal values."""
    if not path.is_file():
        return

    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if "$" in value or "`" in value:
            continue
        if key and value and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    database_url: str
    port: int
    auto_create_tables: bool
    allowed_origins: list[str]
    local_dev_user_email: str
    default_model: str
    openai_api_key: str | None
    openai_api_base_url: str
    anthropic_api_key: str | None
    anthropic_version: str
    claude_api_base_url: str


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
    load_env_file()
    return Settings(
        database_url=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/convo_maker"),
        port=int(os.getenv("PORT", "3000")),
        auto_create_tables=_env_bool("AUTO_CREATE_TABLES", True),
        allowed_origins=_env_list("ALLOWED_ORIGINS", "http://localhost:3000,chrome-extension://*"),
        local_dev_user_email=os.getenv("LOCAL_DEV_USER_EMAIL", "local-dev@convo-maker.test"),
        default_model=os.getenv("DEFAULT_MODEL", "claude-haiku-4-5-20251001"),
        openai_api_key=_env_optional("OPENAI_API_KEY"),
        openai_api_base_url=os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com"),
        anthropic_api_key=_env_optional("ANTHROPIC_API_KEY"),
        anthropic_version=os.getenv("ANTHROPIC_VERSION", "2023-06-01"),
        claude_api_base_url=os.getenv("CLAUDE_API_BASE_URL", "https://api.anthropic.com"),
    )


settings = get_settings()

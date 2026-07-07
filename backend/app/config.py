from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

# Keychain services the relay flow historically used; consulted only when a key
# is in neither the process env nor an env file.
KEYCHAIN_SERVICES = {
    "OPENAI_API_KEY": "convo-maker-openai-api-key",
    "ANTHROPIC_API_KEY": "convo-maker-anthropic-api-key",
}


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


def keychain_secret(service: str) -> str | None:
    if sys.platform != "darwin":
        return None

    try:
        result = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-s", service, "-w"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


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


def secret(name: str) -> str | None:
    """Provider secret by precedence: process env > backend/.env > macOS Keychain."""
    value = _env_optional(name)
    if value:
        return value

    service = KEYCHAIN_SERVICES.get(name)
    return keychain_secret(service) if service else None


def get_settings() -> Settings:
    load_env_file()
    return Settings(
        database_url=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/convo_maker"),
        port=int(os.getenv("PORT", "3000")),
        auto_create_tables=_env_bool("AUTO_CREATE_TABLES", True),
        allowed_origins=_env_list("ALLOWED_ORIGINS", "http://localhost:3000,chrome-extension://*"),
        local_dev_user_email=os.getenv("LOCAL_DEV_USER_EMAIL", "local-dev@convo-maker.test"),
        default_model=os.getenv("DEFAULT_MODEL", "claude-haiku-4-5-20251001"),
        openai_api_key=secret("OPENAI_API_KEY"),
        openai_api_base_url=os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com"),
        anthropic_api_key=secret("ANTHROPIC_API_KEY"),
        anthropic_version=os.getenv("ANTHROPIC_VERSION", "2023-06-01"),
        claude_api_base_url=os.getenv("CLAUDE_API_BASE_URL", "https://api.anthropic.com"),
    )


settings = get_settings()

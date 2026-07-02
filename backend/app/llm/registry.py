from __future__ import annotations

from functools import lru_cache

from .base import ProviderClient
from .claude import ClaudeClient
from .generation import GenConfig
from .openai import OpenAIClient

# Provider routing is by ID prefix, so new/renamed models work without editing this
# file; the provider API is the authority on whether a given ID actually exists.
_PROVIDERS: dict[str, tuple[str, ...]] = {
    "claude": ("claude-",),
    "openai": ("gpt-", "o1", "o3", "o4", "chatgpt-"),
}
_CLIENTS = {"claude": ClaudeClient, "openai": OpenAIClient}

# Reference/enumeration only (e.g. a UI dropdown) — NOT consulted for routing.
KNOWN_MODELS: tuple[str, ...] = (
    "gpt-5.5-pro",
    "gpt-5.5",
    "gpt-5.4-pro",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
)


def provider_for(model_name: str) -> str:
    for provider, prefixes in _PROVIDERS.items():
        if model_name.startswith(prefixes):
            return provider
    raise KeyError(f"cannot resolve a provider for model: {model_name!r}")


@lru_cache(maxsize=None)
def _client(provider: str) -> ProviderClient:
    return _CLIENTS[provider]()


def get_client(model_name: str) -> ProviderClient:
    return _client(provider_for(model_name))


def get_genconfig(model_name: str, **kwargs) -> GenConfig:
    provider_for(model_name)  # validate routing
    return GenConfig(model_name=model_name, **kwargs)

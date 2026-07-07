from __future__ import annotations

from functools import lru_cache

from .base import ProviderClient
from .claude import ClaudeClient
from .openai import OpenAIClient
from .vllm import VLLMClient

# Provider routing is by ID prefix, so new/renamed models work without editing this
# file; the provider API is the authority on whether a given ID actually exists.
_PROVIDERS: dict[str, tuple[str, ...]] = {
    "claude": ("claude-",),
    "openai": ("gpt-", "o1", "o3", "o4", "chatgpt-"),
    "hosted": (VLLMClient.MODEL_PREFIX,),
}
_CLIENTS = {"claude": ClaudeClient, "openai": OpenAIClient, "hosted": VLLMClient}

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
def _client(provider: str, base_url: str | None = None) -> ProviderClient:
    cls = _CLIENTS[provider]
    return cls(base_url=base_url) if base_url is not None else cls()


def get_client(model_name: str) -> ProviderClient:
    provider = provider_for(model_name)
    if provider == "hosted":
        # Self-hosted models may each run on their own vLLM service.
        return _client(provider, VLLMClient.base_url_for(model_name))
    return _client(provider)

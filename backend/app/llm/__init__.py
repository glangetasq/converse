from __future__ import annotations

from .base import Model, ModelError
from .claude import (
    CLAUDE_MODELS,
    ClaudeHaiku45Model,
    ClaudeModel,
    ClaudeMessagesModel,
    ClaudeOpus47Model,
    ClaudeSonnet46Model,
)
from .limiter import LlmCallLimiter
from .openai import (
    OPENAI_MODELS,
    GPT54MiniModel,
    GPT54Model,
    GPT54NanoModel,
    GPT54ProModel,
    GPT55Model,
    GPT55ProModel,
    OpenAIModel,
    OpenAIResponsesModel,
)

MODELS: dict[str, Model] = {model.model_name: model for model in (*OPENAI_MODELS, *CLAUDE_MODELS)}
MODEL_NAMES: tuple[str, ...] = tuple(MODELS)


def get_model(
    model_name: str,
    *,
    base_url: str | None = None,
    relay_base_url: str | None = None,
    timeout_seconds: float | None = None,
) -> Model:
    model = MODELS[model_name]
    if base_url is None and relay_base_url is None and timeout_seconds is None:
        return model

    return model.with_options(
        base_url=base_url,
        relay_base_url=relay_base_url,
        timeout_seconds=timeout_seconds,
    )


__all__ = [
    "CLAUDE_MODELS",
    "MODEL_NAMES",
    "MODELS",
    "OPENAI_MODELS",
    "ClaudeHaiku45Model",
    "ClaudeMessagesModel",
    "ClaudeModel",
    "ClaudeOpus47Model",
    "ClaudeSonnet46Model",
    "GPT54MiniModel",
    "GPT54Model",
    "GPT54NanoModel",
    "GPT54ProModel",
    "GPT55Model",
    "GPT55ProModel",
    "LlmCallLimiter",
    "Model",
    "ModelError",
    "OpenAIModel",
    "OpenAIResponsesModel",
    "get_model",
]

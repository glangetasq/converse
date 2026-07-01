from __future__ import annotations

from typing import Any

from ...llm import GenConfig, LlmCallLimiter, ProviderClient
from ...prompting import SuggestionPromptBuilder
from .core import Candidate, Case


class Arm:
    """A named (builder, client) that turns a Case into a Candidate — the unit
    under A/B comparison (two arms differing only by a RagAugmentor isolate RAG)."""

    def __init__(
        self,
        name: str,
        builder: SuggestionPromptBuilder,
        client: ProviderClient,
        cfg: GenConfig,
    ) -> None:
        self.name = name
        self.builder = builder
        self.client = client
        self.cfg = cfg

    async def run(
        self,
        case: Case,
        repeat_index: int = 0,
        *,
        limiter: LlmCallLimiter | None = None,
    ) -> Candidate:
        # a failed generation is a Candidate with .error, not a raised exception
        try:
            prompt = await self.builder.build(case)
            completion = await self.client.generate(prompt, self.cfg, limiter=limiter)
        except Exception as error:  # noqa: BLE001 — errors are data here
            return Candidate(
                case_id=case.id,
                arm_name=self.name,
                repeat_index=repeat_index,
                text="",
                error=f"{type(error).__name__}: {error}",
            )
        return Candidate(
            case_id=case.id,
            arm_name=self.name,
            repeat_index=repeat_index,
            text=completion.text,
            prompt=prompt,
            usage=completion.usage,
        )

    def spec(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "builder": self.builder.spec(),
            "gen": self.cfg.spec(),
        }

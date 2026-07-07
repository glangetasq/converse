from __future__ import annotations

from typing import Any

from ...llm import ONLINE, GenConfig, LlmExecutionStrategy, ProviderClient
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
        model: str,
        cfg: GenConfig,
    ) -> None:
        self.name = name
        self.builder = builder
        self.client = client
        self.model = model
        self.cfg = cfg

    async def run(
        self,
        case: Case,
        repeat_index: int = 0,
        *,
        execution: LlmExecutionStrategy = ONLINE,
    ) -> Candidate:
        # a failed generation is a Candidate with .error, not a raised exception
        try:
            built = await self.builder.build(case)
            completion = await self.client.generate(built.prompt, self.model, self.cfg, execution=execution)
        except Exception as error:  # noqa: BLE001 — errors are data here
            return self.failed(case, repeat_index, error)
        return self.candidate(case, repeat_index, built, completion)

    def candidate(self, case: Case, repeat_index: int, built: Any, completion: Any) -> Candidate:
        return Candidate(
            case_id=case.id,
            arm_name=self.name,
            repeat_index=repeat_index,
            text=completion.text,
            prompt=built.prompt,
            evidence=built.evidence,
            provenance=built.provenance,
            usage=completion.usage,
        )

    def failed(self, case: Case, repeat_index: int, error: BaseException, *, prompt: str | None = None) -> Candidate:
        return Candidate(
            case_id=case.id,
            arm_name=self.name,
            repeat_index=repeat_index,
            text="",
            prompt=prompt,
            error=f"{type(error).__name__}: {error}",
        )

    def spec(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "model": self.model,
            "builder": self.builder.spec(),
            "gen": self.cfg.spec(),
        }

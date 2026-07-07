from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from ..config import settings
from .base import ModelError, ProviderClient, strip_json_code_fence
from .generation import BatchRequest, Completion, GenConfig


class OpenAIClient(ProviderClient):
    suite = "openai"
    max_temperature = 2.0

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        super().__init__(
            base_url=base_url or settings.openai_api_base_url,
            path="/v1/responses",
            timeout_seconds=timeout_seconds,
        )

    def build_body(self, prompt: str, model: str, cfg: GenConfig) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "input": self.validate_prompt(prompt),
            "store": False,
        }
        if cfg.schema is not None:
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": cfg.schema.get("title", "response"),
                    "strict": True,
                    "schema": cfg.schema,
                }
            }
        return self.apply_sampling(body, cfg)

    def parse(self, raw: dict[str, Any]) -> Completion:
        # Responses `output` is a list of items; reasoning models emit a "reasoning"
        # item before the "message", so scan for the message rather than index [0].
        for item in raw.get("output", []):
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for part in item.get("content", []):
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "refusal":
                    raise ModelError(f"OpenAI refused the request: {part.get('refusal')}", response_body=raw)
                if part.get("type") == "output_text" and part.get("text"):
                    return Completion(
                        text=strip_json_code_fence(part["text"]),
                        usage=raw.get("usage", {}) or {},
                        finish_reason=raw.get("status"),
                        raw=raw,
                    )
        raise ModelError(f"OpenAI response has no output text{self._missing_text_detail(raw)}", response_body=raw)

    @staticmethod
    def _missing_text_detail(raw: dict[str, Any]) -> str:
        status = raw.get("status")
        reason = (raw.get("incomplete_details") or {}).get("reason")
        if status == "incomplete" and reason:
            return f" (status=incomplete, reason={reason})"
        return f" (status={status})" if status else ""

    def build_headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ModelError("OPENAI_API_KEY is required for OpenAI API calls.")
        return {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

    def submit_batch(self, requests: list[BatchRequest]) -> str:
        lines = "\n".join(json.dumps(self._batch_line(r)) for r in requests)
        file_id = self._upload_jsonl(lines.encode("utf-8"))
        body = {"input_file_id": file_id, "endpoint": self.path, "completion_window": "24h"}
        return self._call("POST", "/v1/batches", body=body)["id"]

    def _batch_line(self, req: BatchRequest) -> dict[str, Any]:
        return {
            "custom_id": req.custom_id,
            "method": "POST",
            "url": self.path,
            "body": self.build_body(req.prompt, req.model, req.cfg),
        }

    def batch_done(self, batch_id: str) -> bool:
        status = self._call("GET", f"/v1/batches/{batch_id}").get("status")
        if status in ("failed", "expired", "cancelled", "cancelling"):
            raise ModelError(f"OpenAI batch {batch_id} {status}", response_body={"status": status})
        return status == "completed"

    def batch_results(self, batch_id: str) -> dict[str, tuple[str, Any]]:
        batch = self._call("GET", f"/v1/batches/{batch_id}")
        out: dict[str, tuple[str, Any]] = {}
        if batch.get("output_file_id"):
            for record in self._read_jsonl(batch["output_file_id"]):
                response = record.get("response") or {}
                if record.get("error"):
                    out[record["custom_id"]] = ("error", json.dumps(record["error"]))
                elif response.get("status_code") == 200:
                    out[record["custom_id"]] = ("ok", response.get("body") or {})
                else:
                    out[record["custom_id"]] = ("error", json.dumps(response.get("body")))
        if batch.get("error_file_id"):
            for record in self._read_jsonl(batch["error_file_id"]):
                out.setdefault(
                    record["custom_id"], ("error", json.dumps(record.get("response") or record.get("error")))
                )
        return out

    def _read_jsonl(self, file_id: str) -> list[dict[str, Any]]:
        text = self._call("GET", f"/v1/files/{file_id}/content", expect_json=False)
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def _upload_jsonl(self, content: bytes) -> str:
        boundary = "----convomakerbatchboundary"
        head = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\nbatch\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="batch.jsonl"\r\n'
            f"Content-Type: application/jsonl\r\n\r\n"
        ).encode("utf-8")
        payload = head + content + f"\r\n--{boundary}--\r\n".encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/v1/files",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))["id"]
        except urllib.error.HTTPError as error:
            parsed = self._decode_json_or_text(error.read().decode("utf-8", errors="replace"))
            raise ModelError(
                self._format_http_error(error.code, parsed), status_code=error.code, response_body=parsed
            ) from error
        except urllib.error.URLError as error:
            raise ModelError(f"Unable to reach {self.suite}: {error.reason}") from error

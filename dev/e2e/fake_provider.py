"""Fake OpenAI/Anthropic provider for e2e tests: /v1/messages, /v1/responses, /v1/embeddings."""

from __future__ import annotations

import hashlib
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8990
EMBEDDING_DIM = 1536


def fake_suggestion(model: str, prompt: str) -> str:
    context_marker = "with-context" if "Additional context from the sender" in prompt else "no-context"
    return f"FAKE_SUGGESTION[{model}|{context_marker}] Hi Maya, following up as promised — sending those slots now!"


def embedding_for(text: str) -> list[float]:
    seed = hashlib.sha256(text.encode()).digest()
    return [((seed[i % 32] / 255.0) - 0.5) for i in range(EMBEDDING_DIM)]


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")

        if self.path == "/v1/messages":
            prompt = body.get("messages", [{}])[0].get("content", "")
            payload = {
                "content": [{"type": "text", "text": fake_suggestion(body.get("model", "?"), prompt)}],
                "usage": {"input_tokens": 42, "output_tokens": 24},
                "stop_reason": "end_turn",
            }
        elif self.path == "/v1/responses":
            payload = {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": fake_suggestion(body.get("model", "?"), body.get("input", ""))}
                        ],
                    }
                ],
                "usage": {"input_tokens": 42, "output_tokens": 24},
                "status": "completed",
            }
        elif self.path == "/v1/embeddings":
            texts = body.get("input", [])
            texts = texts if isinstance(texts, list) else [texts]
            payload = {"data": [{"index": i, "embedding": embedding_for(t)} for i, t in enumerate(texts)]}
        else:
            self.send_response(404)
            self.end_headers()
            return

        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print(f"[fake-provider] {fmt % args}")


if __name__ == "__main__":
    print(f"[fake-provider] listening on {PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()

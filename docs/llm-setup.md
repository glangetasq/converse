# Converse LLM setup

All model calls go through the FastAPI backend — the extension never talks to a
provider or holds a key. The relay that previously proxied OpenAI calls is gone.

```
Converse extension  →  backend (localhost:3000)  →  OpenAI / Anthropic APIs
```

## Keys

Provider keys live only in the backend environment (shell env or `backend/.env`):

- `OPENAI_API_KEY` — OpenAI models and the embeddings used by RAG retrieval.
- `ANTHROPIC_API_KEY` — Claude models (the default model is a Claude Haiku).

Missing keys degrade cleanly: generation returns HTTP 502 with the reason, and RAG
falls back to an un-augmented prompt (`ragError` in the response).

## Models

`GET /api/llm/models` serves the menu shown in the extension from
`backend/app/llm/registry.py` (`KNOWN_MODELS`). The default is
`claude-haiku-4-5-20251001`, overridable with the `DEFAULT_MODEL` env var.
Provider routing is by model-id prefix, so new model ids work without code changes.

## Key-free testing

`dev/e2e/fake_provider.py` mimics `/v1/messages`, `/v1/responses` and
`/v1/embeddings`. Point the backend at it to exercise the full generation path
without keys or cost:

```sh
OPENAI_API_KEY=test ANTHROPIC_API_KEY=test \
OPENAI_API_BASE_URL=http://127.0.0.1:8990 CLAUDE_API_BASE_URL=http://127.0.0.1:8990 \
uvicorn app.main:app --port 3001
```

The extension's backend URL can be repointed per-profile via
`chrome.storage.local.set({ backend_url: "http://localhost:3001" })`.

# Converse LLM setup

All model calls go through the FastAPI backend — the extension never talks to a
provider or holds a key. The relay that previously proxied OpenAI calls is gone.

```
Converse extension  →  backend (localhost:3000)  →  OpenAI / Anthropic APIs
```

## Keys

Provider keys are resolved by the backend at startup, in precedence order:

1. process environment
2. `backend/.env` (gitignored, `KEY=value` lines)
3. `~/.zsh_secrets` (`export KEY="value"` lines; non-literal values are skipped)
4. macOS Keychain — services `convo-maker-openai-api-key` and
   `convo-maker-anthropic-api-key` (the same items the old relay used)

- `OPENAI_API_KEY` — OpenAI models and the embeddings used by RAG retrieval.
- `ANTHROPIC_API_KEY` — Claude models (the default model is a Claude Haiku).

Store or refresh a key in the Keychain with:

```sh
security add-generic-password -U -s convo-maker-openai-api-key -a "$USER" -w
security add-generic-password -U -s convo-maker-anthropic-api-key -a "$USER" -w
```

Note: `uvicorn --reload` watches `.py` files only — after changing `.env` or the
Keychain, restart the server (or touch any `.py` file) to re-resolve keys.

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

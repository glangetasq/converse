# Converse LLM setup

## Recommended architecture

Do not put your OpenAI API key directly into the Chrome extension.

Use this flow instead:

1. `Converse extension`
2. `Your local or private relay`
3. `OpenAI API`

The extension should only store:

- relay URL
- request path
- model name

The OpenAI API key should live only on the relay as an environment variable such as `OPENAI_API_KEY`.

## Easiest safe setup for you and a few friends

The safest low-friction setup is:

1. Each person runs their own small local relay.
2. Each person creates their own OpenAI project and API key.
3. Each person stores their own key only in their own machine environment.
4. The extension points to `http://127.0.0.1:8787`.

That keeps the real OpenAI key out of the extension and avoids sharing one powerful key across multiple people.

## Shared relay option

If you want one relay for a few people:

1. Keep the OpenAI key on your server only.
2. Put spend limits and per-user rate limits on the relay.
3. Add real authentication before giving friends access.
4. Prefer HTTPS and a private domain.

Avoid storing any long-lived secret in the extension unless you are comfortable treating it as compromised.

## OpenAI dashboard checklist

1. Create or choose a project in the OpenAI dashboard.
2. Add billing to that project.
3. Set a project budget / spend alert.
4. Create a project API key.
5. Put that key into your relay environment as `OPENAI_API_KEY`.
6. Optionally configure IP allowlisting if your relay runs from a stable server IP.

## Extension wiring

The popup now has an `llm connection` section. Fill in:

- `provider`: `OpenAI Chat Completions`
- `relay url`: usually `http://127.0.0.1:8787` for a local relay
- `path`: `/v1/chat/completions`
- `model`: for example `gpt-4.1-mini`

Then click `save llm settings` and approve the host permission request.

## One-command local relay

Everything needed now lives inside this project.

Start it with:

```bash
./scripts/start-relay.sh
```

On first run the script:

1. asks for your OpenAI API key
2. stores it in the macOS Keychain when available
3. falls back to `relay/.local/openai-api-key` with restricted file permissions if Keychain is unavailable
4. starts the local relay on `http://127.0.0.1:8787`

If you want to replace the stored key later:

```bash
./scripts/start-relay.sh --reset-key
./scripts/start-relay.sh
```

The relay implementation is at `relay/server.mjs`.

## Future providers

The extension now separates:

- provider metadata and defaults in `frontend/llm/config.js`
- provider-specific request/response handling in `frontend/llm/providers/`
- UI and prompt building in `frontend/popup.js`
- network execution and storage in `frontend/background.js`
- extension frontend files in `frontend/`

To add another provider later, create another file in `frontend/llm/providers/`, register it, and save settings for that provider through the same popup flow.

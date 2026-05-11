# Backend TODOs

- Choose the auth story before production. The current FastAPI service creates a local dev user from `LOCAL_DEV_USER_EMAIL`.
- Decide whether the Chrome extension should keep using `relay/` directly for LLM calls or call this API for follow-up generation.
- Wire `/api/followups/generate` to your prompt builder, memory retrieval, and OpenAI relay/client.
- Wire `/api/memory/generate` to message chunking, structured extraction, deduping, and embedding storage.
- Replace placeholder text search in `/api/memory/search` with pgvector similarity search plus optional reranking.
- Add Alembic migrations once the schema stabilizes. `schema.sql` is intentionally simple for the first rebuild.
- Add API tests around conversation import idempotency, feedback writes, and memory search filters.


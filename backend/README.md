# Converse FastAPI backend

This is the Python API for Converse. The extension talks only to this backend; provider keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) live in its environment, resolved at startup from the process env or `backend/.env`.

## Run locally

The database is Neon (serverless Postgres); there is no local database. Point `DATABASE_URL` at the Neon **pooled** url and run the API natively:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
source ../scripts/load_secrets.sh          # exports NEON_POOLED_URL (+ provider keys)
DATABASE_URL="$NEON_POOLED_URL" uvicorn app.main:app --reload --port 3000
```

Keep `AUTO_CREATE_TABLES` unset/false — the schema is loaded out-of-band, not on startup. To apply it to a fresh database, run `sql/*.sql` in numeric order against the **direct** url:

```bash
for f in sql/*.sql; do psql "$NEON_DIRECT_URL" -v ON_ERROR_STOP=1 -f "$f"; done
```

The deployed backend runs on Cloud Run; see `scripts/deploy/backend.sh`.

## Routes

- `GET /health`
- `POST /api/auth/login`
- `POST /api/conversations/import`
- `GET /api/conversations/{id}`
- `GET /api/persons/{id}/memory`
- `POST /api/memory/generate`
- `POST /api/memory/search`
- `POST /api/followups/generate` — RAG prompt + provider call; persists the generation with full reproduction metadata (prompt spec, gen config, thread, retrieved fact ids)
- `POST /api/followups/preview` — the exact generation prompt, no model call
- `POST /api/followups/{id}/ingest` — record the user-approved final draft: accepted/edited flag + original↔final cosine similarity
- `POST /api/followups/{id}/feedback`
- `GET /api/llm/models` — model menu for the extension + default
- `POST /api/eval_examples`
- `POST /api/debug/parse_dump`

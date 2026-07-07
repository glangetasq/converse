# Converse FastAPI backend

This is the Python API for Converse. The extension talks only to this backend; provider keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) live in its environment — see `docs/llm-setup.md`.

## Run locally

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d postgres
uvicorn app.main:app --reload --port 3000
```

Or run the API and database together:

```bash
docker compose up --build
```

The default `AUTO_CREATE_TABLES=true` applies `schema.sql` on startup. You can also apply it manually:

```bash
psql postgresql://postgres:postgres@localhost:5432/convo_maker -f schema.sql
```

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

`postgres_demo.py` shows a minimal write and read using the same tables.

# Converse

Converse is a Chrome extension and backend prototype for generating better follow-up messages from conversation context. The current focus is LinkedIn messaging: parse the visible conversation, build an LLM prompt from the parsed context, generate suggested replies, and evaluate those suggestions against saved examples.

## What It Does

- Opens as a Chrome side panel on supported sites.
- Parses page context from LinkedIn profiles, LinkedIn messages, job postings, and other supported surfaces.
- Builds prompt inputs from the parsed conversation plus user controls such as tone, language, length, and extra instructions.
- Calls an LLM through a local/private relay instead of storing API keys in the extension.
- Stores backend entities such as users, people, conversations, follow-up generations, feedback, and evaluation examples in Postgres.
- Runs an evaluation loop for LinkedIn follow-up suggestions by generating a suggestion, judging it with an LLM, and collecting scores in a pandas DataFrame.

## How It Works

The project has four main parts:

- `frontend/`: Chrome extension UI, side-panel workflow, page parsers, prompt assembly, and suggestion injection.
- `relay/`: local HTTP relay that forwards LLM requests to providers while keeping API keys outside the extension.
- `backend/`: FastAPI service backed by Postgres for conversation data, memory/follow-up routes, and evaluation data.
- `backend/app/evaluation/`: LinkedIn suggestion generation and LLM-as-judge evaluation prompts, schemas, and runner.

The safe LLM path is:

```text
Chrome extension -> local/private relay -> OpenAI/LLM provider
```

For evaluation, the current flow is:

```text
eval example -> suggestion prompt -> model suggestion -> judge prompt -> structured verdict row
```

The evaluator uses structured outputs, bounded concurrency, retries, and a shared LLM call limiter to avoid rate-limit failures.

## Running Locally

Start the local relay:

```bash
./scripts/start-relay.sh
```

Start the backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d postgres
uvicorn app.main:app --reload --port 3000
```

Run the LinkedIn evaluation script:

```bash
cd backend
python -m app.evaluation.linkedin_eval
```

More LLM setup notes live in `docs/llm-setup.md`.

## What Is Left

- Connect the backend `/api/followups/generate` route to the production prompt builder and LLM client.
- Decide whether the extension should call the backend for generation or keep generating directly through the relay.
- Implement real memory generation, retrieval, deduping, embeddings, and reranking.
- Replace development auth with a production-ready auth model.
- Add migrations once the schema stabilizes.
- Add broader API tests around import idempotency, feedback writes, evaluation runs, and memory search.
- Persist evaluation results and add richer analysis/reporting on verdict scores, tone match, and failure cases.

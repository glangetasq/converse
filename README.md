# Converse

Converse is a Chrome extension and backend prototype for generating better follow-up messages from conversation context. The current focus is LinkedIn messaging: it parses the visible conversation, retrieves relevant facts about you and the recipient, and drafts suggested replies grounded in that context — then evaluates those suggestions against saved examples with an LLM-as-judge.

## What It Does

- Opens as a Chrome side panel on LinkedIn profiles, messages, and job postings.
- Parses the on-page conversation and lets you steer tone, language, length, and extra instructions.
- Runs a RAG pipeline that retrieves atomic facts — headlines, common ground, thread-relevant items — to ground each suggestion.
- Serves generation and data through a FastAPI backend backed by Postgres.
- Stores users, people, conversations, follow-up generations, feedback, and evaluation examples.
- Runs an evaluation loop that generates a suggestion, judges it, and collects scores in a DataFrame.

## Analyses

[`notebooks/01_rag_ab_test.ipynb`](notebooks/01_rag_ab_test.ipynb) — an A/B test of the RAG pipeline against a no-RAG baseline, scored by both pointwise and pairwise LLM-as-judge.

Key findings:

- **The pairwise judge prefers RAG 85% of the time**, 67% strictly better — biggest gains in groundedness, clarity, and natural next move.
- Pointwise means barely move, showing why direct pairwise comparison beats scoring each arm on a 1-5 scale.
- Pairwise and pointwise verdicts rarely hard-disagree, which raises confidence in the judge.
- RAG stays preferred across every length and thread-depth bucket, so the uplift isn't a length or conversation-stage artifact.

## How It Works

The backend is organized by domain under `backend/app/`:

- `ingestion/` — parse and reprocess LinkedIn profiles into stored entities.
- `retrieval/` + `prompting/` — RAG search, config, and prompt assembly.
- `llm/` — provider clients, embeddings, execution strategies, and a shared rate limiter.
- `evaluation/` — LinkedIn suggestion generation plus the LLM-as-judge framework and runner.
- `routers/` + `web/` — FastAPI routes and request/response serialization.

The extension lives in `frontend/`: side-panel UI, page parsers, prompt controls, and suggestion injection.

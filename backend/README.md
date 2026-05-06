# Convo Maker Backend

Backend skeleton for the Chrome extension that parses LinkedIn and Gmail conversations. The goal is to move direct OpenAI calls out of the extension and create a stable place for conversation storage, memory, and future RAG workflows.

This is intentionally a skeleton. Conversation import and persistence are wired, but the core AI/RAG behavior is left as explicit TODOs.

## Stack

- Node.js + TypeScript
- Fastify
- Postgres with pgvector
- Drizzle ORM
- Docker Compose
- Vitest

## Local Setup

```bash
cd backend
cp .env.example .env
npm install
npm run db:migrate
npm run dev
```

The API listens on `http://localhost:3000`.

## Docker Compose

```bash
cd backend
cp .env.example .env
docker compose up --build
```

Services:

- Backend: `http://localhost:3000`
- Postgres: `localhost:5432`
- Adminer: `http://localhost:8080`

Adminer connection values:

- System: `PostgreSQL`
- Server: `postgres`
- Username: `postgres`
- Password: `postgres`
- Database: `convo_maker`

## Database

Generate a migration after changing `src/db/schema.ts`:

```bash
npm run db:generate
```

Apply migrations:

```bash
npm run db:migrate
```

The initial migration enables the `vector` extension and creates:

- `users`
- `persons`
- `conversations`
- `messages`
- `memory_items`
- `followup_generations`

`memory_items.embedding` is a nullable `vector(1536)` column.

## Tests

```bash
npm test
```

The current tests use Fastify injection and service fakes for fast skeleton coverage. Add database integration tests when the persistence layer starts carrying more behavior.

## API Endpoints

- `GET /health`
- `POST /api/conversations/import`
- `GET /api/conversations/:id`
- `GET /api/persons/:id/memory`
- `POST /api/memory/generate`
- `POST /api/memory/search`
- `POST /api/followups/generate`
- `POST /api/followups/:id/feedback`

## Import Payload Shape

```json
{
  "source": "linkedin",
  "externalThreadId": "linkedin-thread-id",
  "rawUrl": "https://www.linkedin.com/messaging/thread/example",
  "title": "Conversation title",
  "person": {
    "fullName": "Ada Lovelace",
    "email": "ada@example.com",
    "linkedinUrl": "https://www.linkedin.com/in/ada",
    "company": "Analytical Engines Ltd",
    "roleTitle": "Founder"
  },
  "messages": [
    {
      "sourceMessageId": "message-1",
      "senderName": "Ada Lovelace",
      "senderType": "contact",
      "body": "Hello!",
      "sentAt": "2026-01-01T12:00:00.000Z",
      "messageOrder": 0,
      "metadata": {}
    }
  ]
}
```

## Core AI TODOs

- TODO: conversation normalization
- TODO: entity/person resolution
- TODO: message chunking
- TODO: structured memory extraction
- TODO: embedding storage pipeline
- TODO: pgvector retrieval
- TODO: hybrid reranking
- TODO: prompt assembly
- TODO: follow-up generation logic
- TODO: feedback/evaluation loop

## Notes

- `src/middleware/devUser.ts` creates or finds a default local user.
- `src/services/openaiClient.ts` only contains low-level OpenAI wrapper calls.
- Higher-level memory and follow-up services intentionally return placeholders until the AI workflow is implemented.

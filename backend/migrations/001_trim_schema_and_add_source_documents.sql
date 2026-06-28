-- Migration 001: trim stale/unused columns, add source_documents, align memory_items.
--
-- Brings an existing database in line with schema.sql after:
--   * persons        — drop company, role_title (queried from another table to avoid staleness)
--   * source_documents — new append-only raw source-of-truth table (did not exist before)
--   * memory_items   — drop importance_score, confidence_score, valid_from, valid_until,
--                      metadata, updated_at; add source_document_id; add missing indexes
--
-- Safety: persons is preserved with ALTER (it holds real rows). memory_items is recreated
-- from the canonical definition, guarded by an emptiness check so it can never silently
-- drop data. Re-runnable: IF EXISTS / IF NOT EXISTS guards make a second run a no-op
-- (except the guarded memory_items recreate, which is idempotent on an empty table).

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. persons: drop columns that go stale.
ALTER TABLE persons DROP COLUMN IF EXISTS company;
ALTER TABLE persons DROP COLUMN IF EXISTS role_title;

-- 2. source_documents: append-only raw source of truth for curated facts.
CREATE TABLE IF NOT EXISTS source_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  person_id uuid REFERENCES persons(id) ON DELETE CASCADE,
  kind text NOT NULL,                 -- 'linkedin_profile' | 'self_profile' | 'resume' | 'note'
  source text NOT NULL,               -- 'linkedin' | 'manual' | 'resume_import'
  source_url text,
  content jsonb NOT NULL,             -- parser JSON verbatim, or {"markdown": "..."} for free text
  raw_text text,                      -- optional flattened text (debug + future hybrid full-text search)
  content_hash text NOT NULL,         -- skip ingesting identical re-scrapes
  captured_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS source_documents_user_person_idx
  ON source_documents(user_id, person_id);

CREATE UNIQUE INDEX IF NOT EXISTS source_documents_user_content_hash_idx
  ON source_documents(user_id, content_hash);

-- 3. memory_items: recreate to match canonical schema.
--    Guard against destroying data — this DB has it empty, but fail loudly otherwise.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM memory_items LIMIT 1) THEN
    RAISE EXCEPTION
      'memory_items is not empty; aborting destructive recreate. Migrate its columns by hand.';
  END IF;
END $$;

DROP TABLE IF EXISTS memory_items;

CREATE TABLE memory_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  person_id uuid REFERENCES persons(id) ON DELETE SET NULL,
  conversation_id uuid REFERENCES conversations(id) ON DELETE SET NULL,
  message_id uuid REFERENCES messages(id) ON DELETE SET NULL,
  source_document_id uuid REFERENCES source_documents(id) ON DELETE CASCADE,
  memory_type text NOT NULL,
  content text NOT NULL,
  content_hash text NOT NULL,
  source text NOT NULL,
  embedding vector(1536),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memory_items_user_person_idx
  ON memory_items(user_id, person_id);

CREATE UNIQUE INDEX IF NOT EXISTS memory_items_user_content_hash_idx
  ON memory_items(user_id, content_hash);

CREATE INDEX IF NOT EXISTS memory_items_source_document_idx
  ON memory_items(source_document_id);

-- Approximate-nearest-neighbour index for retrieval (cosine distance: embedding <=> query).
CREATE INDEX IF NOT EXISTS memory_items_embedding_hnsw_idx
  ON memory_items USING hnsw (embedding vector_cosine_ops);

COMMIT;

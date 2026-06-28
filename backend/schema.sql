CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text UNIQUE,
  display_name text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS persons (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  full_name text,
  normalized_name text,
  linkedin_url text,
  email text,
  source_first_seen text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS persons_user_email_idx ON persons(user_id, email);
CREATE INDEX IF NOT EXISTS persons_user_linkedin_idx ON persons(user_id, linkedin_url);

-- Re-processable source of truth for curated facts: append-only raw snapshots.
-- Recipient LinkedIn profiles (person_id set) AND the user's own resume/projects/notes
-- (person_id NULL). The parser output (or authored markdown) is stored verbatim in
-- `content`; atomic, embedded facts are derived into memory_items, which point back here
-- via source_document_id so we can re-atomize/re-embed without re-scraping.
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

CREATE TABLE IF NOT EXISTS conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  person_id uuid REFERENCES persons(id) ON DELETE SET NULL,
  source text NOT NULL,
  external_thread_id text,
  title text,
  raw_url text,
  started_at timestamptz,
  last_message_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS conversations_user_source_thread_idx
  ON conversations(user_id, source, external_thread_id);

CREATE TABLE IF NOT EXISTS messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  person_id uuid REFERENCES persons(id) ON DELETE SET NULL,
  source_message_id text,
  sender_name text,
  sender_type text NOT NULL DEFAULT 'unknown',
  body text NOT NULL,
  sent_at timestamptz,
  message_order integer NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS messages_conversation_order_idx
  ON messages(conversation_id, message_order);

CREATE UNIQUE INDEX IF NOT EXISTS messages_conversation_source_message_idx
  ON messages(conversation_id, source_message_id);

CREATE TABLE IF NOT EXISTS memory_items (
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

CREATE TABLE IF NOT EXISTS followup_generations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  person_id uuid REFERENCES persons(id) ON DELETE SET NULL,
  conversation_id uuid REFERENCES conversations(id) ON DELETE SET NULL,
  user_prompt text,
  tone text,
  target_length text,
  retrieved_memory_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  model_name text,
  generated_text text NOT NULL,
  user_feedback text,
  final_sent_text text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

---- HUMAN TABLE ----
CREATE TABLE IF NOT EXISTS eval_examples (
      id                         SERIAL PRIMARY KEY,
      eval_thread_id             INT NOT NULL,
      user_id                    UUID NOT NULL REFERENCES users(id),
      recipient_id               UUID REFERENCES persons(id),
      source                     VARCHAR(16) NOT NULL,
      past_context               JSONB NOT NULL,
      ground_truth_reply         TEXT NOT NULL,
      ground_truth_time          TIMESTAMPTZ,
      quality_rating             INT,
      quality_rating_time        TIMESTAMPTZ NOT NULL DEFAULT now(),
      recipient_replied          BOOLEAN,
      recipient_quality_rating   INT,

      CONSTRAINT quality_rating_range
          CHECK (quality_rating IS NULL OR quality_rating BETWEEN 1 AND 5),
      CONSTRAINT recipient_quality_rating_range
          CHECK (recipient_quality_rating IS NULL OR recipient_quality_rating BETWEEN 1 AND 5)
  );

CREATE INDEX IF NOT EXISTS idx_eval_examples_recipient       ON eval_examples (user_id, recipient_id);
CREATE INDEX IF NOT EXISTS idx_eval_examples_source          ON eval_examples (user_id, source);

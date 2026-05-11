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
  company text,
  role_title text,
  source_first_seen text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS persons_user_email_idx ON persons(user_id, email);
CREATE INDEX IF NOT EXISTS persons_user_linkedin_idx ON persons(user_id, linkedin_url);

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
  memory_type text NOT NULL,
  content text NOT NULL,
  content_hash text NOT NULL,
  importance_score real NOT NULL DEFAULT 0.5,
  confidence_score real NOT NULL DEFAULT 1,
  source text NOT NULL,
  valid_from timestamptz NOT NULL DEFAULT now(),
  valid_until timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  embedding vector(1536),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memory_items_user_person_idx
  ON memory_items(user_id, person_id);

CREATE UNIQUE INDEX IF NOT EXISTS memory_items_user_content_hash_idx
  ON memory_items(user_id, content_hash);

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


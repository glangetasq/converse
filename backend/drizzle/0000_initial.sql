CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS "users" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "email" text UNIQUE,
  "display_name" text,
  "created_at" timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS "persons" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "user_id" uuid NOT NULL REFERENCES "users"("id") ON DELETE cascade,
  "full_name" text,
  "normalized_name" text,
  "linkedin_url" text,
  "email" text,
  "company" text,
  "role_title" text,
  "source_first_seen" text,
  "created_at" timestamp with time zone DEFAULT now() NOT NULL,
  "updated_at" timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS "conversations" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "user_id" uuid NOT NULL REFERENCES "users"("id") ON DELETE cascade,
  "person_id" uuid REFERENCES "persons"("id") ON DELETE set null,
  "source" text NOT NULL,
  "external_thread_id" text,
  "title" text,
  "raw_url" text,
  "started_at" timestamp with time zone,
  "last_message_at" timestamp with time zone,
  "created_at" timestamp with time zone DEFAULT now() NOT NULL,
  "updated_at" timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS "messages" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "conversation_id" uuid NOT NULL REFERENCES "conversations"("id") ON DELETE cascade,
  "user_id" uuid NOT NULL REFERENCES "users"("id") ON DELETE cascade,
  "person_id" uuid REFERENCES "persons"("id") ON DELETE set null,
  "source_message_id" text,
  "sender_name" text,
  "sender_type" text DEFAULT 'unknown' NOT NULL,
  "body" text NOT NULL,
  "sent_at" timestamp with time zone,
  "message_order" integer NOT NULL,
  "metadata" jsonb DEFAULT '{}'::jsonb NOT NULL,
  "created_at" timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS "memory_items" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "user_id" uuid NOT NULL REFERENCES "users"("id") ON DELETE cascade,
  "person_id" uuid REFERENCES "persons"("id") ON DELETE set null,
  "conversation_id" uuid REFERENCES "conversations"("id") ON DELETE set null,
  "message_id" uuid REFERENCES "messages"("id") ON DELETE set null,
  "memory_type" text NOT NULL,
  "content" text NOT NULL,
  "content_hash" text NOT NULL,
  "importance_score" real DEFAULT 0.5 NOT NULL,
  "confidence_score" real DEFAULT 1 NOT NULL,
  "source" text NOT NULL,
  "valid_from" timestamp with time zone DEFAULT now() NOT NULL,
  "valid_until" timestamp with time zone,
  "metadata" jsonb DEFAULT '{}'::jsonb NOT NULL,
  "embedding" vector(1536),
  "created_at" timestamp with time zone DEFAULT now() NOT NULL,
  "updated_at" timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS "followup_generations" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "user_id" uuid NOT NULL REFERENCES "users"("id") ON DELETE cascade,
  "person_id" uuid REFERENCES "persons"("id") ON DELETE set null,
  "conversation_id" uuid REFERENCES "conversations"("id") ON DELETE set null,
  "user_prompt" text,
  "tone" text,
  "target_length" text,
  "retrieved_memory_ids" jsonb DEFAULT '[]'::jsonb NOT NULL,
  "model_name" text,
  "generated_text" text NOT NULL,
  "user_feedback" text,
  "final_sent_text" text,
  "metadata" jsonb DEFAULT '{}'::jsonb NOT NULL,
  "created_at" timestamp with time zone DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS "persons_user_email_idx" ON "persons" ("user_id", "email");
CREATE INDEX IF NOT EXISTS "persons_user_linkedin_idx" ON "persons" ("user_id", "linkedin_url");
CREATE UNIQUE INDEX IF NOT EXISTS "conversations_user_source_thread_idx" ON "conversations" ("user_id", "source", "external_thread_id");
CREATE INDEX IF NOT EXISTS "messages_conversation_order_idx" ON "messages" ("conversation_id", "message_order");
CREATE UNIQUE INDEX IF NOT EXISTS "messages_conversation_source_message_idx" ON "messages" ("conversation_id", "source_message_id");
CREATE INDEX IF NOT EXISTS "memory_items_user_person_idx" ON "memory_items" ("user_id", "person_id");
CREATE UNIQUE INDEX IF NOT EXISTS "memory_items_user_content_hash_idx" ON "memory_items" ("user_id", "content_hash");

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

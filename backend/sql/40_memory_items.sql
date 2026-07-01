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

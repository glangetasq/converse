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

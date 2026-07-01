-- Human-curated gold set: past_context + ground_truth_reply per eval thread.
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

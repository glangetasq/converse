-- 004 — Add followup_generations.original_final_similarity: cosine similarity between
-- the generated suggestion and the user-approved final draft, written by the ingest
-- endpoint. A real column (not metadata jsonb) so it is directly queryable.
-- Backfills from metadata for rows ingested before this migration.
-- Re-run is a no-op (IF NOT EXISTS; backfill only touches NULL columns).
--     psql "$DATABASE_URL" -f migrations/004_followup_generations_similarity.sql

\set ON_ERROR_STOP on
BEGIN;

ALTER TABLE followup_generations
  ADD COLUMN IF NOT EXISTS original_final_similarity real;

UPDATE followup_generations
SET original_final_similarity = (metadata->>'originalFinalSimilarity')::real
WHERE original_final_similarity IS NULL
  AND jsonb_typeof(metadata->'originalFinalSimilarity') = 'number';

COMMIT;

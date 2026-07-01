-- 003 — Add eval_runs.judge_specs (Judge.spec() per judge), symmetric to arm_specs.
-- Existing runs default to '[]'. Re-run is a no-op (IF NOT EXISTS).
--     psql "$DATABASE_URL" -f migrations/003_eval_runs_judge_specs.sql

\set ON_ERROR_STOP on
BEGIN;

ALTER TABLE eval_runs
  ADD COLUMN IF NOT EXISTS judge_specs jsonb NOT NULL DEFAULT '[]'::jsonb;

COMMIT;

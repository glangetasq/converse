-- ============================================================================
-- 002 — Realign the eval corpus + self-profile onto the LocalDev user, and
--       merge the name-only eval recipient persons into the ingested profile
--       persons so RAG retrieval keys line up (plan item p3-9).
--
-- BEFORE (the bug, see backend/checks/p3-9/):
--   * eval_examples (101 rows / 14 recipients) + self-profile (1 doc, 30
--     user-facts) live under user "Quentin Glangetas"
--     (quentin.glangetas@converse.local), created by the eval-save path passing
--     the real sender name as the account.
--   * The 14 LinkedIn profiles (14 docs + 115 person memories) were ingested
--     under the LocalDev user (local-dev@convo-maker.test) as SEPARATE persons
--     that carry linkedin_url. find_or_create_person matched only by url/email,
--     so it never reused the name-only eval recipient persons.
--   => person_id keys are disjoint: every eval recipient has 0 memories.
--
-- AFTER: everything lives under the LocalDev user; the ingested persons (which
-- own the docs + memories + linkedin_url) are canonical; eval_examples point at
-- them; the 14 name-only Quentin persons and the empty Quentin user are dropped.
--
-- Decisions (confirmed 2026-06-30): keep ingested persons + re-point eval;
-- decouple the eval account (LocalDev) from the sender name ("Quentin
-- Glangetas", still used for ground-truth matching in code).
--
-- Users are resolved by email via inline subselects (robust to differing UUIDs).
-- A re-run is a safe no-op: once the Quentin user is gone, every subselect is
-- NULL and the UPDATE/DELETEs match nothing. Wrapped in one transaction with
-- pre/post-condition guards; any surprise raises and rolls the whole thing back.
--     psql "$DATABASE_URL" -f migrations/002_realign_eval_and_self_profile_to_dev_user.sql
-- ============================================================================

\set ON_ERROR_STOP on
BEGIN;

-- ---- Precondition guard: every Quentin recipient must have a same-name LocalDev
-- ---- person to merge into; otherwise we'd orphan eval rows on delete. -----------
DO $$
DECLARE
  quentin_id  uuid := (SELECT id FROM users WHERE email = 'quentin.glangetas@converse.local');
  localdev_id uuid := (SELECT id FROM users WHERE email = 'local-dev@convo-maker.test');
  unmatched   int;
BEGIN
  IF localdev_id IS NULL THEN
    RAISE EXCEPTION 'Abort: local-dev user not found.';
  END IF;
  IF quentin_id IS NULL THEN
    RAISE NOTICE 'Quentin user already absent — migration is a no-op.';
    RETURN;
  END IF;

  SELECT count(*) INTO unmatched
  FROM (SELECT DISTINCT recipient_id FROM eval_examples
        WHERE user_id = quentin_id AND recipient_id IS NOT NULL) er
  JOIN persons q ON q.id = er.recipient_id
  LEFT JOIN persons ld
    ON ld.user_id = localdev_id AND ld.normalized_name = q.normalized_name
  WHERE ld.id IS NULL;

  IF unmatched > 0 THEN
    RAISE EXCEPTION
      'Abort: % eval recipient(s) have no same-name LocalDev person to merge into.', unmatched;
  END IF;
END $$;

-- ---- 1. Re-point eval_examples.recipient_id: name-only Quentin person ----------
-- ----    -> ingested LocalDev person (same normalized_name). Done first, while ---
-- ----    the rows are still under Quentin, so the join keys are unambiguous. -----
UPDATE eval_examples e
SET recipient_id = ld.id
FROM persons q
JOIN persons ld
  ON ld.normalized_name = q.normalized_name
 AND ld.user_id = (SELECT id FROM users WHERE email = 'local-dev@convo-maker.test')
WHERE e.recipient_id = q.id
  AND q.user_id = (SELECT id FROM users WHERE email = 'quentin.glangetas@converse.local');

-- ---- 2. Move the eval corpus itself onto the LocalDev account. ------------------
UPDATE eval_examples
SET user_id = (SELECT id FROM users WHERE email = 'local-dev@convo-maker.test')
WHERE user_id = (SELECT id FROM users WHERE email = 'quentin.glangetas@converse.local');

-- ---- 3. Move the self-profile document + its user-facts (person_id NULL) --------
-- ----    onto the LocalDev account so they retrieve alongside person facts. ------
UPDATE source_documents
SET user_id = (SELECT id FROM users WHERE email = 'local-dev@convo-maker.test')
WHERE user_id = (SELECT id FROM users WHERE email = 'quentin.glangetas@converse.local')
  AND kind = 'self_profile';

UPDATE memory_items
SET user_id = (SELECT id FROM users WHERE email = 'local-dev@convo-maker.test')
WHERE user_id = (SELECT id FROM users WHERE email = 'quentin.glangetas@converse.local')
  AND person_id IS NULL;

-- ---- Guard: the Quentin user must now be fully drained before we delete it. -----
DO $$
DECLARE
  quentin_id uuid := (SELECT id FROM users WHERE email = 'quentin.glangetas@converse.local');
  evals int; docs int; mems int;
BEGIN
  IF quentin_id IS NULL THEN RETURN; END IF;  -- already migrated

  SELECT count(*) INTO evals FROM eval_examples    WHERE user_id = quentin_id;
  SELECT count(*) INTO docs  FROM source_documents WHERE user_id = quentin_id;
  SELECT count(*) INTO mems  FROM memory_items     WHERE user_id = quentin_id;

  IF evals <> 0 OR docs <> 0 OR mems <> 0 THEN
    RAISE EXCEPTION
      'Abort: Quentin user not fully drained (eval=%, docs=%, mems=%).', evals, docs, mems;
  END IF;
END $$;

-- ---- 4. Drop the now-unreferenced name-only recipient persons. The FK on -------
-- ----    eval_examples.recipient_id (NO ACTION) makes this fail loudly if any ----
-- ----    eval row still points here — a final safety net for step 1. ------------
DELETE FROM persons
WHERE user_id = (SELECT id FROM users WHERE email = 'quentin.glangetas@converse.local');

-- ---- 5. Drop the empty Quentin user. -------------------------------------------
DELETE FROM users WHERE email = 'quentin.glangetas@converse.local';

-- ---- Post-condition report (inside the tx, before COMMIT). ----------------------
\echo '== post-migration: eval recipients now resolve to person memories =='
SELECT
  count(*)                            AS eval_recipients,
  count(*) FILTER (WHERE mem.cnt > 0) AS recipients_with_memories,
  count(*) FILTER (WHERE mem.cnt = 0) AS recipients_fail
FROM (SELECT DISTINCT user_id, recipient_id FROM eval_examples) e
CROSS JOIN LATERAL (
  SELECT count(*) AS cnt FROM memory_items m WHERE m.person_id = e.recipient_id
) mem;

\echo '== post-migration: user-facts (person_id NULL) now under LocalDev =='
SELECT u.display_name, count(*) AS user_facts
FROM memory_items m JOIN users u ON u.id = m.user_id
WHERE m.person_id IS NULL
GROUP BY u.display_name;

COMMIT;

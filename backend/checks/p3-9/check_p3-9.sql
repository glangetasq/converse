-- ============================================================================
-- p3-9 manual check: "Match each profile to the eval_examples recipient /
--                     persons row so retrieval keys line up."
--
-- Retrieval (Phase 4) will key person-facts by:
--     memory_items.person_id  ==  eval_examples.recipient_id   (same user_id)
-- and user-facts by person_id IS NULL under that same user_id.
--
-- This file PROVES (or disproves) that those keys actually line up TODAY.
--
-- RISK (why this check exists): find_or_create_person() dedupes only by
-- linkedin_url / email, else INSERTs a fresh row. Eval recipients may have been
-- seeded name-only (no linkedin_url) while ingested profiles carry a
-- linkedin_url -> the same human can become TWO persons rows, and the profile's
-- memories would hang off a person_id the eval never references.
-- Also: persons has 14 rows under BOTH the local-dev user AND Quentin.
--
-- Run:   psql "$DATABASE_URL" -f check_p3-9.sql
--   or:  ./run.sh            (wrapper, see run.sh)
--
-- Read each section's RESULT line. A clean pass = every "FAIL"/"ORPHAN"/
-- "MISSING" count is 0 and Q9's verdict row shows matched == recipients.
-- ============================================================================

\pset pager off
\timing off

-- ----------------------------------------------------------------------------
-- Q0. Who's who: list users so we can fix the canonical user_id by eye.
--     Expect the eval owner = "Quentin Glangetas" (id ~ 95e7b569...) and a
--     separate local-dev user (~ 79c19af9...).
-- ----------------------------------------------------------------------------
\echo '== Q0: users =='
SELECT id, email, display_name, created_at
FROM users
ORDER BY created_at;

-- ----------------------------------------------------------------------------
-- Q1. Per-user inventory. EVERYTHING on the eval path must sit under ONE
--     user_id. If persons/source_documents/memory_items/eval_examples are
--     split across two user_ids, retrieval will silently return nothing.
-- ----------------------------------------------------------------------------
\echo '== Q1: per-user inventory (persons / docs / memories / eval) =='
SELECT
  u.id                                                            AS user_id,
  u.display_name,
  (SELECT count(*) FROM persons p           WHERE p.user_id = u.id)                          AS persons,
  (SELECT count(*) FROM source_documents sd WHERE sd.user_id = u.id
                                              AND sd.kind = 'linkedin_profile')              AS linkedin_docs,
  (SELECT count(*) FROM source_documents sd WHERE sd.user_id = u.id
                                              AND sd.kind = 'self_profile')                  AS self_docs,
  (SELECT count(*) FROM memory_items m      WHERE m.user_id = u.id
                                              AND m.person_id IS NOT NULL)                   AS person_memories,
  (SELECT count(*) FROM memory_items m      WHERE m.user_id = u.id
                                              AND m.person_id IS NULL)                       AS user_memories,
  (SELECT count(*)              FROM eval_examples e WHERE e.user_id = u.id)                 AS eval_rows,
  (SELECT count(DISTINCT recipient_id) FROM eval_examples e WHERE e.user_id = u.id)          AS eval_recipients
FROM users u
ORDER BY u.created_at;

-- ----------------------------------------------------------------------------
-- Q2. The eval recipients themselves: distinct recipient_id in eval_examples,
--     resolved to their persons row. linkedin_url tells us whether
--     find_or_create_person could have matched an ingested profile.
-- ----------------------------------------------------------------------------
\echo '== Q2: distinct eval recipients (with person row + linkedin_url) =='
SELECT
  e.user_id,
  e.recipient_id,
  p.full_name,
  p.normalized_name,
  NULLIF(p.linkedin_url, '')         AS linkedin_url,
  count(*)                           AS eval_threads,
  (p.id IS NULL)                     AS person_row_missing
FROM eval_examples e
LEFT JOIN persons p ON p.id = e.recipient_id
GROUP BY e.user_id, e.recipient_id, p.full_name, p.normalized_name, p.linkedin_url, p.id
ORDER BY p.full_name NULLS FIRST;

-- ----------------------------------------------------------------------------
-- Q3. *** THE CORE JOIN ***  For every eval recipient, is there a
--     linkedin_profile source_document AND person-memories keyed to that exact
--     recipient_id? person_facts_for_recipient = 0 means retrieval finds
--     NOTHING for that person.
-- ----------------------------------------------------------------------------
\echo '== Q3: eval recipient -> profile doc -> person memories (per recipient) =='
SELECT
  p.full_name,
  e.recipient_id,
  (SELECT count(*) FROM source_documents sd
     WHERE sd.person_id = e.recipient_id AND sd.kind = 'linkedin_profile')   AS profile_docs,
  (SELECT count(*) FROM memory_items m
     WHERE m.person_id = e.recipient_id)                                     AS person_memories,
  CASE
    WHEN (SELECT count(*) FROM memory_items m WHERE m.person_id = e.recipient_id) = 0
      THEN 'FAIL: no memories for this recipient'
    WHEN (SELECT count(*) FROM source_documents sd
            WHERE sd.person_id = e.recipient_id AND sd.kind = 'linkedin_profile') = 0
      THEN 'WARN: memories exist but no profile doc keyed here'
    ELSE 'ok'
  END AS verdict
FROM (SELECT DISTINCT user_id, recipient_id FROM eval_examples) e
LEFT JOIN persons p ON p.id = e.recipient_id
ORDER BY verdict, p.full_name;

-- ----------------------------------------------------------------------------
-- Q4. ORPHAN profiles: ingested linkedin_profile docs whose person_id is NOT
--     referenced by any eval recipient. These are the "duplicate person row"
--     casualties -- their memories will never be retrieved by the eval.
-- ----------------------------------------------------------------------------
\echo '== Q4: orphan linkedin_profile docs (person_id not an eval recipient) =='
SELECT
  sd.id            AS source_document_id,
  sd.user_id,
  sd.person_id,
  p.full_name,
  NULLIF(p.linkedin_url, '') AS linkedin_url
FROM source_documents sd
LEFT JOIN persons p ON p.id = sd.person_id
WHERE sd.kind = 'linkedin_profile'
  AND NOT EXISTS (
        SELECT 1 FROM eval_examples e
        WHERE e.recipient_id = sd.person_id
      )
ORDER BY p.full_name NULLS FIRST;

-- ----------------------------------------------------------------------------
-- Q5. Duplicate persons WITHIN a user by normalized_name -- the smoking gun for
--     "same human, two person rows" (one the eval points at, one the profile
--     points at). Any row here means keys are split.
-- ----------------------------------------------------------------------------
\echo '== Q5: duplicate person rows (same normalized_name, same user) =='
SELECT
  user_id,
  normalized_name,
  count(*)                                   AS person_rows,
  array_agg(id ORDER BY created_at)          AS person_ids,
  array_agg(DISTINCT NULLIF(linkedin_url,'')) AS linkedin_urls
FROM persons
WHERE normalized_name IS NOT NULL
GROUP BY user_id, normalized_name
HAVING count(*) > 1
ORDER BY person_rows DESC, normalized_name;

-- ----------------------------------------------------------------------------
-- Q6. Cross-check the same name as an EVAL recipient vs a PROFILE-doc person.
--     If both columns are non-null but the ids differ -> split keys for that
--     human (this is the precise failure Phase 4 would hit).
-- ----------------------------------------------------------------------------
\echo '== Q6: same name, eval recipient id vs profile-doc person id =='
WITH eval_people AS (
  SELECT DISTINCT p.user_id, p.normalized_name, e.recipient_id
  FROM eval_examples e JOIN persons p ON p.id = e.recipient_id
),
doc_people AS (
  SELECT DISTINCT p.user_id, p.normalized_name, sd.person_id
  FROM source_documents sd JOIN persons p ON p.id = sd.person_id
  WHERE sd.kind = 'linkedin_profile'
)
SELECT
  COALESCE(ep.user_id, dp.user_id)        AS user_id,
  COALESCE(ep.normalized_name, dp.normalized_name) AS normalized_name,
  ep.recipient_id                         AS eval_recipient_id,
  dp.person_id                            AS profile_person_id,
  CASE
    WHEN ep.recipient_id IS NULL THEN 'profile has no eval thread'
    WHEN dp.person_id   IS NULL THEN 'eval recipient has no profile doc'
    WHEN ep.recipient_id = dp.person_id THEN 'ALIGNED'
    ELSE 'SPLIT: eval and profile point at different person rows'
  END AS verdict
FROM eval_people ep
FULL OUTER JOIN doc_people dp
  ON ep.user_id = dp.user_id AND ep.normalized_name = dp.normalized_name
ORDER BY verdict, normalized_name;

-- ----------------------------------------------------------------------------
-- Q7. User-fact (self-profile) sanity: person_id NULL memories under the eval
--     owner, plus the self_profile doc. Phase 4 retrieves these as "about you".
-- ----------------------------------------------------------------------------
\echo '== Q7: self-profile / user facts under each user =='
SELECT
  u.id AS user_id,
  u.display_name,
  (SELECT count(*) FROM source_documents sd
     WHERE sd.user_id = u.id AND sd.kind = 'self_profile')                AS self_profile_docs,
  (SELECT count(*) FROM memory_items m
     WHERE m.user_id = u.id AND m.person_id IS NULL)                      AS user_facts,
  (SELECT string_agg(DISTINCT m.memory_type, ', ' ORDER BY m.memory_type)
     FROM memory_items m
     WHERE m.user_id = u.id AND m.person_id IS NULL)                      AS user_memory_types
FROM users u
ORDER BY u.created_at;

-- ----------------------------------------------------------------------------
-- Q8. Every person-memory must have an embedding (retrieval is vector-only).
--     Any NULL embedding here = silently un-retrievable fact.
-- ----------------------------------------------------------------------------
\echo '== Q8: memories missing an embedding =='
SELECT
  user_id,
  (person_id IS NULL) AS is_user_fact,
  count(*)            AS rows_missing_embedding
FROM memory_items
WHERE embedding IS NULL
GROUP BY user_id, (person_id IS NULL)
ORDER BY user_id;

-- ----------------------------------------------------------------------------
-- Q9. *** VERDICT *** one-line pass/fail per user: of the distinct eval
--     recipients, how many have >=1 person-memory keyed to their recipient_id?
--     PASS when matched == recipients (and user_facts > 0 for the eval owner).
-- ----------------------------------------------------------------------------
\echo '== Q9: VERDICT -- eval recipients with retrievable person memories =='
SELECT
  e.user_id,
  u.display_name,
  count(*)                                                    AS eval_recipients,
  count(*) FILTER (WHERE mem.cnt > 0)                          AS recipients_with_memories,
  count(*) FILTER (WHERE mem.cnt = 0)                          AS recipients_FAIL,
  (SELECT count(*) FROM memory_items m
     WHERE m.user_id = e.user_id AND m.person_id IS NULL)      AS user_facts,
  CASE WHEN count(*) FILTER (WHERE mem.cnt = 0) = 0
       THEN 'PASS: every eval recipient has retrievable person memories'
       ELSE 'FAIL: some eval recipients have no memories -> keys not aligned'
  END AS verdict
FROM (SELECT DISTINCT user_id, recipient_id FROM eval_examples) e
JOIN users u ON u.id = e.user_id
CROSS JOIN LATERAL (
  SELECT count(*) AS cnt FROM memory_items m WHERE m.person_id = e.recipient_id
) mem
GROUP BY e.user_id, u.display_name
ORDER BY u.display_name;

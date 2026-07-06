-- Machine eval results, written by evaluation.framework.results.save_run.
--
-- Reproducibility model: a run_id reconstructs to the exact inputs that produced it.
-- Everything versioned is snapshotted here as jsonb (not referenced by id), so a run
-- stays readable after the prompt/scorecard files move on. Three versioning axes:
--   * text  -> content fingerprint (utils.fingerprint, sha256[:12]) of the prompt /
--              scorecard bytes -- the derived truth a hand-typed tag is checked against.
--   * human -> the `version` tag someone bumps by hand (e.g. 'v1'); fingerprint wins on disagreement.
--   * code  -> Judge.logic_version -- the aggregation/ordering methodology, distinct from text.
CREATE TABLE IF NOT EXISTS eval_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan text NOT NULL,                 -- 'pointwise' | 'pairwise'
  samples integer NOT NULL,
  label text,
  -- what GENERATED the run: Arm.spec() per arm, in order (arms[0]='a')
  --   {name, model, builder: {version, fingerprint, augment}, gen: GenConfig (sampling only)}
  arm_specs jsonb NOT NULL,
  -- what SCORED it, symmetric to arm_specs: Judge.spec() per judge
  --   {name, mode, model, logic_version, gen, prompt (fingerprinted for template builders), scorecard: {version, fingerprint, metrics}}
  judge_specs jsonb NOT NULL DEFAULT '[]'::jsonb,
  meta jsonb NOT NULL DEFAULT '{}'::jsonb,  -- meta.git = {commit, dirty}: the harness commit that ran it
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eval_candidates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
  candidate_key text NOT NULL,        -- Candidate.id: 'case_id::arm_name::repeat_index'
  case_id text NOT NULL,
  arm_name text NOT NULL,             -- joins to the producing arm in eval_runs.arm_specs[].name
  repeat_index integer NOT NULL,
  text text NOT NULL,
  prompt text,
  usage jsonb NOT NULL DEFAULT '{}'::jsonb,
  error text,
  UNIQUE (run_id, candidate_key)
);

CREATE INDEX IF NOT EXISTS eval_candidates_run_idx ON eval_candidates(run_id);

CREATE TABLE IF NOT EXISTS eval_judgements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
  judge_name text NOT NULL,           -- joins to the scoring judge in eval_runs.judge_specs[].name
  mode text NOT NULL,                 -- 'pointwise' | 'pairwise'
  scorecard_version text NOT NULL,    -- human tag, denormalized; full scorecard (incl fingerprint) in judge_specs
  subject_candidate_id text,          -- pointwise: the scored candidate_key
  candidate_a_id text,                -- pairwise: the 'a'/'b' candidate_keys
  candidate_b_id text,
  scores jsonb,                       -- pointwise: {metric: int}
  preference jsonb,                   -- pairwise: {metric: 'a'|'b'|'tie'}
  verdict text,
  winner text,
  rationale text,
  error text
);

CREATE INDEX IF NOT EXISTS eval_judgements_run_idx ON eval_judgements(run_id);

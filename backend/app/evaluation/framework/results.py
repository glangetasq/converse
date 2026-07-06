"""The Postgres half of the pipeline: run_eval -> EvalRun -> save_run -> run_id
-> load_run(run_id). The only framework module that touches app.db."""

from __future__ import annotations

import pandas as pd
from psycopg.types.json import Json

from ... import db
from .core import Candidate, PairwiseJudgement, PointwiseJudgement
from .runner import EvalRun


def _insert(table: str, cols: tuple[str, ...]) -> str:
    fields = ", ".join(cols)
    values = ", ".join(f"%({c})s" for c in cols)
    return f"INSERT INTO {table} ({fields}) VALUES ({values})"


async def _write(cur, table: str, rows: list[dict], *, returning: str | None = None):
    """Insert rows given as {column: value} dicts — columns are the first row's keys, so
    the field definition (the dict) is also the query. `returning` inserts the single row
    and returns that column (used for the run's generated id)."""
    if not rows:
        return None
    sql = _insert(table, tuple(rows[0]))
    if returning:
        await cur.execute(f"{sql} RETURNING {returning}", rows[0])
        return (await cur.fetchone())[returning]
    await cur.executemany(sql, rows)
    return None


def _run_row(run: EvalRun) -> dict:
    return {
        "plan": run.plan,
        "samples": run.samples,
        "label": run.label,
        "arm_specs": Json(run.arm_specs),
        "judge_specs": Json(run.judge_specs),
        "meta": Json(run.meta),
    }


def _candidate_row(run_id: str, c: Candidate) -> dict:
    return {
        "run_id": run_id,
        "candidate_key": c.id,
        "case_id": c.case_id,
        "arm_name": c.arm_name,
        "repeat_index": c.repeat_index,
        "text": c.text,
        "prompt": c.prompt,
        "usage": Json(c.usage),
        "error": c.error,
    }


def _judgement_row(run_id: str, j: PointwiseJudgement | PairwiseJudgement) -> dict:
    row = {
        "run_id": run_id,
        "judge_name": j.judge_name,
        "mode": None,
        "scorecard_version": j.scorecard_version,
        "rationale": j.rationale,
        "error": j.error,
        "subject_candidate_id": None,
        "candidate_a_id": None,
        "candidate_b_id": None,
        "scores": None,
        "preference": None,
        "verdict": None,
        "winner": None,
    }
    if isinstance(j, PointwiseJudgement):  # each branch fills only its mode's columns
        row.update(
            mode="pointwise",
            subject_candidate_id=j.subject_candidate_id,
            scores=Json(j.scores),
            verdict=j.verdict,
        )
    else:
        row.update(
            mode="pairwise",
            candidate_a_id=j.candidate_a_id,
            candidate_b_id=j.candidate_b_id,
            preference=Json(j.preference),
            winner=j.winner,
        )
    return row


async def run_exists(run_id: str) -> bool:
    return await db.fetch_one("SELECT 1 FROM eval_runs WHERE id = %s", (run_id,)) is not None


async def save_run(run: EvalRun) -> str:
    """Insert the run and its children in one transaction; return the new run_id."""
    async for conn in db.connection():
        async with conn.cursor() as cur:
            run_id = str(await _write(cur, "eval_runs", [_run_row(run)], returning="id"))
            await _write(
                cur,
                "eval_candidates",
                [_candidate_row(run_id, c) for c in run.candidates],
            )
            await _write(
                cur,
                "eval_judgements",
                [_judgement_row(run_id, j) for j in run.judgements],
            )
        await conn.commit()
    return run_id


def _len_cols(alias: str, suffix: str = "") -> str:
    """chars + whitespace word count for `alias`.text, suffixed per candidate side."""
    txt = f"{alias}.text"
    words = f"CASE WHEN btrim({txt}) = '' THEN 0 ELSE array_length(regexp_split_to_array(btrim({txt}), '\\s+'), 1) END"
    return f"length({txt}) AS chars{suffix}, {words} AS words{suffix}"


def _expand_json_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Flatten a 1-level dict column ({metric: value}) into one column per key, in place
    of the original. Assumes non-list dict values; no-op if the column is absent/empty.
    """
    if column not in df.columns or df.empty:
        return df
    expanded = pd.json_normalize(df[column]).set_index(df.index)
    return pd.concat([df.drop(columns=[column]), expanded], axis=1)


async def _read_pointwise(run_id: str) -> pd.DataFrame:
    df = pd.DataFrame(
        await db.fetch_all(
            f"""
        SELECT c.case_id, c.arm_name, c.repeat_index, {_len_cols("c")},
               j.judge_name, j.scorecard_version, j.scores, j.verdict, j.rationale, j.error
        FROM eval_judgements j
        JOIN eval_candidates c
          ON c.run_id = j.run_id AND c.candidate_key = j.subject_candidate_id
        WHERE j.run_id = %s
        ORDER BY c.case_id, c.repeat_index, j.judge_name
    """,
            (run_id,),
        )
    )
    return _expand_json_column(df, "scores")


async def _read_pairwise(run_id: str) -> pd.DataFrame:
    df = pd.DataFrame(
        await db.fetch_all(
            f"""
        SELECT a.case_id, a.repeat_index, a.arm_name AS arm_a, b.arm_name AS arm_b,
               {_len_cols("a", "_a")}, {_len_cols("b", "_b")},
               j.judge_name, j.scorecard_version, j.preference, j.winner, j.rationale, j.error
        FROM eval_judgements j
        JOIN eval_candidates a ON a.run_id = j.run_id AND a.candidate_key = j.candidate_a_id
        JOIN eval_candidates b ON b.run_id = j.run_id AND b.candidate_key = j.candidate_b_id
        WHERE j.run_id = %s
        ORDER BY a.case_id, a.repeat_index, j.judge_name
    """,
            (run_id,),
        )
    )
    return _expand_json_column(df, "preference")


async def load_run(run_id: str) -> pd.DataFrame:
    """One row per judgement, joined to its candidate(s). Shape follows the run's plan."""
    run = await db.fetch_one("SELECT plan FROM eval_runs WHERE id = %s", (run_id,))
    if run is None:
        raise LookupError(f"no eval run {run_id!r}")
    read = _read_pointwise if run["plan"] == "pointwise" else _read_pairwise
    return await read(run_id)

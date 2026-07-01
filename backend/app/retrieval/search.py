from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Mapping, Sequence

import numpy as np

from .. import db
from ..llm.embeddings import get_embedder
from ..utils import render_thread
from .config import DEFAULT_CONFIG, RetrievalConfig

# memory_type anchors for Channel H (see ingestion/linkedin_profile + self_profile).
PERSON_HEADLINE_TYPE = "headline"
USER_HEADLINE_TYPE = "user.headline"

FactLabel = Literal["about_you", "about_them", "shared_ground"]


# --- data shapes -----------------------------------------------------------------
@dataclass
class FactRow:
    id: str
    person_id: str | None
    memory_type: str
    content: str
    created_at: datetime
    embedding: np.ndarray         # raw pgvector text on the way in, ndarray after init

    def __post_init__(self) -> None:
        self.id = str(self.id)
        self.person_id = str(self.person_id) if self.person_id is not None else None
        self.embedding = self._parse_vector(self.embedding)

    @staticmethod
    def _parse_vector(raw: Any) -> np.ndarray:
        """pgvector column ('[1,2,3]' text) -> float32 ndarray; ndarray/list pass through."""
        if isinstance(raw, np.ndarray):
            return raw.astype(np.float32, copy=False)
        if isinstance(raw, str):
            raw = json.loads(raw)   # pgvector text form is a valid JSON array
        return np.asarray(raw, dtype=np.float32)

    @property
    def is_user_fact(self) -> bool:
        return self.person_id is None

    @property
    def is_headline_fact(self) -> bool:
        return self.memory_type == USER_HEADLINE_TYPE or self.memory_type == PERSON_HEADLINE_TYPE

    @property
    def label(self) -> FactLabel:
        return "about_you" if self.is_user_fact else "about_them"


@dataclass
class ScoredFact:
    fact: FactRow
    similarity: float             # cosine similarity in [-1, 1] (1 - distance)

    @classmethod
    def from_db_result(cls, **kwargs):
        distance = kwargs.pop("distance")
        return cls(FactRow(**kwargs), similarity=1 - distance)


@dataclass
class CommonGroundPair:
    """A user fact and the recipient fact it most resembles (Channel C)."""

    user_fact: FactRow
    person_fact: FactRow
    similarity: float


@dataclass
class RetrievedFact:
    """A fact selected for the prompt, with its provenance label for phrasing."""

    fact: FactRow
    label: FactLabel
    score: float | None = None
    matched: FactRow | None = None   # set when label == "shared_ground"


async def embed_query(text: str) -> list[float]:
    """Embed one query string -> n-d vector."""
    embedder = get_embedder()
    embeddings = await embedder.embed([text])
    return embeddings[0] if embeddings else []


# --- the single DB source: both pools, relevance-scored ---------------------------
async def search_facts(
    user_id: str,
    query_embedding: Sequence[float],
    *,
    person_id: str | None = None,
) -> list[ScoredFact]:
    """Query all fact candidates"""
    vector = "[" + ",".join([repr(float(x)) for x in query_embedding]) + "]"
    sql = """
    SELECT
        id,
        content,
        person_id,
        memory_type,
        created_at,
        embedding,
        embedding <=> %s::vector AS distance
    FROM memory_items
    WHERE user_id=%s AND (person_id IS NULL or person_id=%s)
    ORDER BY distance ASC
    """
    facts = await db.fetch_all(sql, (vector, user_id, person_id))
    scored_facts = [ScoredFact.from_db_result(**fact) for fact in facts if fact]
    return scored_facts


def split_headlines(facts: Sequence[ScoredFact]) -> tuple[list[ScoredFact], list[FactRow]]:
    headlines = [sf.fact for sf in facts if sf.fact.is_headline_fact]
    non_headlines = [sf for sf in facts if not sf.fact.is_headline_fact]
    return non_headlines, headlines


def split_user_person_facts(facts: Sequence[ScoredFact]) -> tuple[list[FactRow], list[FactRow]]:
    user_facts = [sf.fact for sf in facts if sf.fact.is_user_fact]
    person_facts = [sf.fact for sf in facts if not sf.fact.is_user_fact]
    return user_facts, person_facts


# --- Channel H: headlines (deterministic, from the single result) -----------------
def select_headlines(headlines: Sequence[FactRow]) -> list[RetrievedFact]:
    """Pick the recipient headline + the user headline out of the search result."""
    retrieved_headlines = []

    user_headlines = [fact for fact in headlines if fact.is_user_fact]
    if user_headlines:
        user_headlines.sort(key=lambda fact: fact.created_at, reverse=True)
        retrieved_headlines.append(RetrievedFact(fact=user_headlines[0], label="about_you"))

    person_headlines = [fact for fact in headlines if not fact.is_user_fact]
    if person_headlines:
        person_headlines.sort(key=lambda fact: fact.created_at, reverse=True)
        retrieved_headlines.append(RetrievedFact(fact=person_headlines[0], label="about_them"))

    return retrieved_headlines


# --- Channel C: common ground (pure, fact<->fact) --------------------------------
def common_ground(
    user_facts: Sequence[FactRow],
    person_facts: Sequence[FactRow],
    config: RetrievalConfig = DEFAULT_CONFIG,
) -> list[CommonGroundPair]:
    """Best cross-matches between the two fact sets (shared experience/school/skill)."""
    if not user_facts or not person_facts:
        return []

    user_embeddings = np.stack([fact.embedding for fact in user_facts])
    person_embeddings = np.stack([fact.embedding for fact in person_facts])
    cosine_matrix = _cosine_matrix(user_embeddings, person_embeddings)

    # (similarity, user_idx, person_idx) for each user fact's best person fact, strongest first
    candidates = sorted(
        (
            (float(cosine_matrix[i, j]), i, int(j))
            for i, j in enumerate(cosine_matrix.argmax(axis=1))
        ),
        reverse=True,
    )

    # one pass: dedup on the person side (first occurrence is the best), threshold, cap
    pairs: list[CommonGroundPair] = []
    seen_person: set[int] = set()
    for similarity, i, j in candidates:
        if similarity < config.min_common_ground_sim or j in seen_person:
            continue
        seen_person.add(j)
        pairs.append(CommonGroundPair(user_facts[i], person_facts[j], similarity))
        if len(pairs) == config.common_ground_limit:
            break

    return pairs


def _cosine_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Row-wise cosine similarity matrix between stacked vectors a (n×d), b (m×d).

    Returns an (n×m) matrix where [i, j] = cosine(a[i], b[j])
    """
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    if a.size == 0 or b.size == 0:
        return np.zeros((len(a), len(b)), dtype=np.float32)

    a_norm = np.linalg.norm(a, axis=1, keepdims=True)
    b_norm = np.linalg.norm(b, axis=1, keepdims=True)
    a_unit = a / np.where(a_norm == 0.0, 1.0, a_norm)
    b_unit = b / np.where(b_norm == 0.0, 1.0, b_norm)
    return a_unit @ b_unit.T


# --- the blend -------------------------------------------------------------------
def _calculate_depth_alpha_beta(
    depth: int,
    config: RetrievalConfig = DEFAULT_CONFIG,
) -> tuple[float, float]:
    """Relevance weight alpha(d) = d / (d + k0); beta = 1 - alpha"""
    k0 = config.k0
    assert k0 > 0
    if depth == 0:
        return 0.0, 1.0
    alpha = depth / (depth + k0)
    return alpha, 1.0 - alpha


async def retrieve_facts_for_thread(
    user_id: str,
    person_id: str,
    thread: Sequence[Mapping[str, Any]],
    *,
    config: RetrievalConfig = DEFAULT_CONFIG,
) -> list[RetrievedFact]:
    """
      * H (headlines): always included, never blended (split out first).
      * R (relevance): each ScoredFact.similarity = its thread relevance.
      * C (common ground): per-fact best cross-similarity to the other pool.
    Non-headline score = alpha*relevance + beta*commonground; a fact appears once.
    """
    thread_depth = len(thread)
    query_text = render_thread(thread, fmt="{sender_name} said:\n{body}", recent_n=config.recent_n)
    query_embedding = await embed_query(query_text)
    scored_facts = await search_facts(user_id=user_id, query_embedding=query_embedding, person_id=person_id)
    scored_facts, headlines = split_headlines(scored_facts)

    retrieved_headlines = select_headlines(headlines)

    user_facts, person_facts = split_user_person_facts(scored_facts)
    cg_pairs = common_ground(user_facts, person_facts, config)

    # map a fact id -> its best common-ground match (similarity + the counterpart fact)
    cg_by_fact: dict[str, tuple[float, FactRow]] = {}
    for pair in cg_pairs:
        cg_by_fact[pair.user_fact.id] = (pair.similarity, pair.person_fact)
        cg_by_fact[pair.person_fact.id] = (pair.similarity, pair.user_fact)

    alpha, beta = _calculate_depth_alpha_beta(thread_depth, config)
    relevance_term = {sf.fact.id: alpha * sf.similarity for sf in scored_facts}

    blended: list[RetrievedFact] = []
    consumed: set[str] = set()

    # shared-ground items first: one per winning pair, consuming BOTH facts so
    # neither reappears solo. A pair wins when its CG score beats either side's.
    for pair in cg_pairs:
        common_ground_term = beta * pair.similarity
        best_relevance_term = min(relevance_term[pair.user_fact.id], relevance_term[pair.person_fact.id])
        if common_ground_term < best_relevance_term:
            continue
        blended.append(
            RetrievedFact(
                fact=pair.user_fact,
                label="shared_ground",
                score=common_ground_term + best_relevance_term,
                matched=pair.person_fact,
            )
        )
        consumed.add(pair.user_fact.id)
        consumed.add(pair.person_fact.id)

    # solo items for everything not consumed; common ground still nudges the score.
    for sf in scored_facts:
        fact = sf.fact
        if fact.id in consumed:
            continue
        cg_similarity, _ = cg_by_fact.get(fact.id, (0.0, None))
        blended.append(
            RetrievedFact(
                fact=fact,
                label=fact.label,
                score=relevance_term[fact.id] + beta * cg_similarity,
            )
        )

    blended.sort(key=lambda rf: rf.score, reverse=True)
    remaining = max(0, config.k - len(retrieved_headlines))
    return retrieved_headlines + blended[:remaining]

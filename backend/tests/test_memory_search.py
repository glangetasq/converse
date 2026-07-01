from __future__ import annotations

import asyncio
import unittest
from datetime import datetime
from typing import Any
from unittest import mock

import numpy as np

from app import db
from app.retrieval import search as ms


def make_fact(
    id: str,
    *,
    person_id: str | None = None,
    memory_type: str = "user.project",
    embedding: Any = (1.0, 0.0),
    created_at: datetime | None = None,
) -> ms.FactRow:
    return ms.FactRow(
        id=id,
        person_id=person_id,
        memory_type=memory_type,
        content=f"content-{id}",
        created_at=created_at or datetime(2026, 1, 1),
        embedding=list(embedding) if isinstance(embedding, tuple) else embedding,
    )


def scored(id: str, similarity: float, **kwargs: Any) -> ms.ScoredFact:
    return ms.ScoredFact(make_fact(id, **kwargs), similarity)


# --- FactRow ---------------------------------------------------------------------
class FactRowTests(unittest.TestCase):
    def test_parse_vector_from_pgvector_text(self) -> None:
        v = ms.FactRow._parse_vector("[1.0,2.0,3.0]")
        self.assertEqual(v.dtype, np.float32)
        self.assertEqual(v.tolist(), [1.0, 2.0, 3.0])

    def test_parse_vector_passthrough_ndarray_and_list(self) -> None:
        arr = np.array([1, 2], dtype=np.float64)
        self.assertEqual(ms.FactRow._parse_vector(arr).dtype, np.float32)
        self.assertEqual(ms.FactRow._parse_vector([1, 2]).tolist(), [1.0, 2.0])

    def test_post_init_casts_ids_and_parses_embedding(self) -> None:
        fact = ms.FactRow(
            id=123, person_id=None, memory_type="user.skill",
            content="c", created_at=datetime(2026, 1, 1), embedding="[0.1,0.2]",
        )
        self.assertEqual(fact.id, "123")
        self.assertIsNone(fact.person_id)
        self.assertIsInstance(fact.embedding, np.ndarray)

    def test_property_flags_and_label(self) -> None:
        user = make_fact("u", person_id=None, memory_type="user.headline")
        person = make_fact("p", person_id="r", memory_type="headline")
        self.assertTrue(user.is_user_fact)
        self.assertFalse(person.is_user_fact)
        self.assertEqual(user.label, "about_you")
        self.assertEqual(person.label, "about_them")
        self.assertTrue(user.is_headline_fact)
        self.assertTrue(person.is_headline_fact)
        self.assertFalse(make_fact("x", memory_type="user.project").is_headline_fact)


class ScoredFactTests(unittest.TestCase):
    def test_from_db_result_pops_distance_and_computes_similarity(self) -> None:
        sf = ms.ScoredFact.from_db_result(
            id="x", person_id=None, memory_type="user.project",
            content="c", created_at=datetime(2026, 1, 1), embedding="[1,0]", distance=0.25,
        )
        self.assertAlmostEqual(sf.similarity, 0.75)
        self.assertEqual(sf.fact.id, "x")


# --- _cosine_matrix --------------------------------------------------------------
class CosineMatrixTests(unittest.TestCase):
    def test_values(self) -> None:
        a = np.array([[1, 0, 0], [0, 1, 0]], float)
        b = np.array([[1, 0, 0], [1, 1, 0], [0, 0, 1]], float)
        m = ms._cosine_matrix(a, b)
        self.assertEqual(m.shape, (2, 3))
        self.assertAlmostEqual(m[0, 0], 1.0, places=4)
        self.assertAlmostEqual(m[0, 1], 0.7071, places=4)
        self.assertAlmostEqual(m[0, 2], 0.0, places=4)

    def test_empty_sides_give_shaped_zero(self) -> None:
        b = np.array([[1, 0, 0]], float)
        self.assertEqual(ms._cosine_matrix(np.zeros((0, 3)), b).shape, (0, 1))
        self.assertEqual(ms._cosine_matrix([], b).shape, (0, 1))

    def test_zero_row_is_not_nan(self) -> None:
        a = np.array([[0, 0, 0], [1, 0, 0]], float)
        b = np.array([[1, 0, 0]], float)
        m = ms._cosine_matrix(a, b)
        self.assertFalse(np.isnan(m).any())
        self.assertEqual(m[0, 0], 0.0)


# --- _calculate_depth_alpha_beta -------------------------------------------------
class DepthAlphaBetaTests(unittest.TestCase):
    def test_zero_depth_all_common_ground(self) -> None:
        self.assertEqual(ms._calculate_depth_alpha_beta(0), (0.0, 1.0))

    def test_midpoint_at_k0(self) -> None:
        alpha, beta = ms._calculate_depth_alpha_beta(4, ms.RetrievalConfig(k0=4.0))
        self.assertAlmostEqual(alpha, 0.5)
        self.assertAlmostEqual(beta, 0.5)

    def test_alpha_grows_and_beta_complements(self) -> None:
        a_small, _ = ms._calculate_depth_alpha_beta(2)
        a_big, b_big = ms._calculate_depth_alpha_beta(100)
        self.assertLess(a_small, a_big)
        self.assertAlmostEqual(a_big + b_big, 1.0)


# --- split helpers ---------------------------------------------------------------
class SplitTests(unittest.TestCase):
    def test_split_headlines(self) -> None:
        facts = [
            scored("uh", 0.1, person_id=None, memory_type="user.headline"),
            scored("ph", 0.1, person_id="r", memory_type="headline"),
            scored("u1", 0.9, person_id=None, memory_type="user.project"),
        ]
        non_headlines, headlines = ms.split_headlines(facts)
        self.assertEqual([sf.fact.id for sf in non_headlines], ["u1"])
        self.assertEqual(sorted(f.id for f in headlines), ["ph", "uh"])

    def test_split_user_person_facts(self) -> None:
        facts = [scored("u", 0.5, person_id=None), scored("p", 0.5, person_id="r")]
        user_facts, person_facts = ms.split_user_person_facts(facts)
        self.assertEqual([f.id for f in user_facts], ["u"])
        self.assertEqual([f.id for f in person_facts], ["p"])


# --- select_headlines ------------------------------------------------------------
class SelectHeadlinesTests(unittest.TestCase):
    def test_picks_freshest_per_side_with_labels(self) -> None:
        headlines = [
            make_fact("uh_old", person_id=None, memory_type="user.headline", created_at=datetime(2025, 1, 1)),
            make_fact("uh_new", person_id=None, memory_type="user.headline", created_at=datetime(2026, 6, 1)),
            make_fact("ph", person_id="r", memory_type="headline", created_at=datetime(2026, 1, 1)),
        ]
        out = ms.select_headlines(headlines)
        by_label = {rf.label: rf.fact.id for rf in out}
        self.assertEqual(by_label, {"about_you": "uh_new", "about_them": "ph"})

    def test_tolerates_missing_side(self) -> None:
        out = ms.select_headlines([make_fact("ph", person_id="r", memory_type="headline")])
        self.assertEqual([rf.label for rf in out], ["about_them"])

    def test_empty(self) -> None:
        self.assertEqual(ms.select_headlines([]), [])


# --- common_ground ---------------------------------------------------------------
class CommonGroundTests(unittest.TestCase):
    def test_empty_pool_returns_empty(self) -> None:
        self.assertEqual(ms.common_ground([], [make_fact("p", person_id="r")]), [])

    def test_person_side_dedup_keeps_strongest(self) -> None:
        # u0 and u1 both best-match p0; only the stronger pair survives.
        u = [make_fact("u0", embedding=(1, 0, 0)), make_fact("u1", embedding=(0.9, 0.1, 0))]
        p = [make_fact("p0", person_id="r", embedding=(1, 0, 0))]
        pairs = ms.common_ground(u, p, ms.RetrievalConfig(min_common_ground_sim=0.3))
        self.assertEqual(len(pairs), 1)
        self.assertEqual((pairs[0].user_fact.id, pairs[0].person_fact.id), ("u0", "p0"))

    def test_threshold_drops_weak_pairs(self) -> None:
        u = [make_fact("u0", embedding=(1, 0, 0))]
        p = [make_fact("p0", person_id="r", embedding=(0, 1, 0))]  # orthogonal -> sim 0
        self.assertEqual(ms.common_ground(u, p, ms.RetrievalConfig(min_common_ground_sim=0.5)), [])

    def test_limit_caps_results(self) -> None:
        # distinct one-hot dims so each user fact best-matches its own person fact
        # (5 distinct pairs), then limit caps the result.
        eye = np.eye(5)
        u = [make_fact(f"u{i}", embedding=eye[i]) for i in range(5)]
        p = [make_fact(f"p{i}", person_id="r", embedding=eye[i]) for i in range(5)]
        cfg = ms.RetrievalConfig(common_ground_limit=2, min_common_ground_sim=0.3)
        self.assertEqual(len(ms.common_ground(u, p, cfg)), 2)

    def test_similarity_is_plain_float(self) -> None:
        u = [make_fact("u0", embedding=(1, 0))]
        p = [make_fact("p0", person_id="r", embedding=(1, 0))]
        pairs = ms.common_ground(u, p, ms.RetrievalConfig(min_common_ground_sim=0.3))
        self.assertIsInstance(pairs[0].similarity, float)


# --- search_facts (db stubbed) ---------------------------------------------------
class SearchFactsTests(unittest.TestCase):
    def test_maps_rows_and_binds_vector_and_person(self) -> None:
        captured: dict[str, Any] = {}

        async def fake_fetch_all(sql: str, params: Any) -> list[dict[str, Any]]:
            captured["sql"], captured["params"] = sql, params
            return [
                dict(id="a", person_id=None, memory_type="user.project",
                     content="c", created_at=datetime(2026, 1, 1), embedding="[1,0]", distance=0.2),
            ]

        with mock.patch.object(db, "fetch_all", fake_fetch_all):
            out = asyncio.run(ms.search_facts("U", [1.0, 0.0], person_id="r"))

        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0].similarity, 0.8)
        # vector literal is bound first, person_id passed through
        self.assertEqual(captured["params"][0], "[1.0,0.0]")
        self.assertIn("U", captured["params"])
        self.assertIn("r", captured["params"])


# --- retrieve_facts_for_thread (orchestrator) ------------------------------------
class RetrieveFactsForThreadTests(unittest.TestCase):
    """search_facts + embed_query are stubbed so the blend logic is tested in isolation."""

    def _run(self, scored_facts: list[ms.ScoredFact], *, depth: int, k: int = 8):
        async def fake_embed(text: str) -> list[float]:
            return [1.0, 0.0]

        async def fake_search(user_id, query_embedding, *, person_id=None):
            return scored_facts

        thread = [{"sender_name": "x", "body": "y"} for _ in range(depth)]
        with mock.patch.object(ms, "embed_query", fake_embed), \
                mock.patch.object(ms, "search_facts", fake_search):
            return asyncio.run(ms.retrieve_facts_for_thread("U", "r", thread, config=ms.RetrievalConfig(k=k)))

    def _shared_ground_facts(self) -> list[ms.ScoredFact]:
        # user/person facts that cross-match (cos 0.7), plus a headline on each side
        pa = (0.7, np.sqrt(1 - 0.49))
        return [
            scored("uh", 0.1, person_id=None, memory_type="user.headline", embedding=(0, 0, 1)),
            scored("ph", 0.1, person_id="r", memory_type="headline", embedding=(0, 0, 1)),
            scored("user_a", 0.9, person_id=None, memory_type="user.project", embedding=(1, 0, 0)),
            scored("person_a", 0.5, person_id="r", memory_type="role", embedding=(pa[0], pa[1], 0)),
        ]

    def test_headlines_always_present_both_depths(self) -> None:
        for depth in (0, 12):
            out = self._run(self._shared_ground_facts(), depth=depth)
            ids = {rf.fact.id for rf in out}
            self.assertIn("uh", ids)
            self.assertIn("ph", ids)

    def test_no_fact_surfaces_twice(self) -> None:
        # regression for the shared-ground dedup bug: a fact must not appear both
        # solo and as another item's `matched` counterpart.
        out = self._run(self._shared_ground_facts(), depth=4)
        surfaced: list[str] = []
        for rf in out:
            surfaced.append(rf.fact.id)
            if rf.matched is not None:
                surfaced.append(rf.matched.id)
        self.assertEqual(len(surfaced), len(set(surfaced)), surfaced)

    def test_cold_open_surfaces_shared_ground(self) -> None:
        out = self._run(self._shared_ground_facts(), depth=0)
        labels = {rf.label for rf in out}
        self.assertIn("shared_ground", labels)
        sg = next(rf for rf in out if rf.label == "shared_ground")
        self.assertIsNotNone(sg.matched)

    def test_deep_thread_is_relevance_labeled(self) -> None:
        # at large depth, relevance dominates -> the matched pair is shown as solo
        # about_you / about_them, not shared_ground.
        out = self._run(self._shared_ground_facts(), depth=200)
        non_headline = [rf for rf in out if not rf.fact.is_headline_fact]
        self.assertTrue(all(rf.label != "shared_ground" for rf in non_headline))
        self.assertTrue(all(rf.matched is None for rf in non_headline))

    def test_k_cap_respected(self) -> None:
        facts = [scored("uh", 0.1, person_id=None, memory_type="user.headline", embedding=(0, 1))]
        facts += [scored(f"u{i}", 0.5 - i * 0.01, person_id=None, embedding=(1, 0)) for i in range(10)]
        out = self._run(facts, depth=5, k=4)
        self.assertEqual(len(out), 4)


if __name__ == "__main__":
    unittest.main()

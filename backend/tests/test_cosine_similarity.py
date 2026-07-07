from __future__ import annotations

import unittest

from app.utils import cosine_similarity


class CosineSimilarityTests(unittest.TestCase):
    def test_identical_vectors(self) -> None:
        self.assertAlmostEqual(cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]), 1.0)

    def test_orthogonal_vectors(self) -> None:
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_opposite_vectors(self) -> None:
        self.assertAlmostEqual(cosine_similarity([1.0, -2.0], [-1.0, 2.0]), -1.0)

    def test_scale_invariant(self) -> None:
        self.assertAlmostEqual(cosine_similarity([1.0, 1.0], [10.0, 10.0]), 1.0)

    def test_rejects_mismatched_or_empty(self) -> None:
        with self.assertRaises(ValueError):
            cosine_similarity([1.0], [1.0, 2.0])
        with self.assertRaises(ValueError):
            cosine_similarity([], [])

    def test_rejects_zero_vector(self) -> None:
        with self.assertRaises(ValueError):
            cosine_similarity([0.0, 0.0], [1.0, 2.0])


if __name__ == "__main__":
    unittest.main()

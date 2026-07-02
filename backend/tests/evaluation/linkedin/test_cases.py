from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from app.evaluation.linkedin import cases as cases_mod
from app.evaluation.linkedin.cases import load_cases


class LoadCasesTests(unittest.TestCase):
    def test_maps_rows_to_cases_with_depth_and_ids(self) -> None:
        rows = [
            {
                "id": 1,
                "user_id": "u1",
                "recipient_id": "p1",
                "past_context": [{"sender_name": "A", "body": "hi"}],
                "ground_truth_reply": "yo",
                "quality_rating": 4,
            },
            {
                "id": 2,
                "user_id": "u1",
                "recipient_id": None,
                "past_context": [{"body": "m"}] * 6,
                "ground_truth_reply": "sure",
                "quality_rating": None,
            },
        ]
        with patch("app.db.fetch_all", return_value=rows), patch.object(
            cases_mod, "get_user_id_to_name_dict", return_value={"u1": "Alice"}
        ), patch.object(cases_mod, "get_person_id_to_name_dict", return_value={"p1": "Bob"}):
            result = asyncio.run(load_cases())

        c1, c2 = result
        self.assertEqual((c1.id, c1.sender_name, c1.recipient_name), ("1", "Alice", "Bob"))
        self.assertEqual(c1.meta, {"user_id": "u1", "person_id": "p1", "thread_depth": 1, "quality": 4})
        self.assertEqual(c2.recipient_name, "unknown name")  # missing recipient falls back
        self.assertIsNone(c2.meta["person_id"])
        self.assertEqual(c2.meta["thread_depth"], 6)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import asyncio
import unittest

from app.config import settings
from app.llm import KNOWN_MODELS
from app.routers.llm import list_models


class ListModelsTests(unittest.TestCase):
    def test_default_model_is_listed(self) -> None:
        response = asyncio.run(list_models())
        model_ids = [model["id"] for model in response["models"]]

        self.assertEqual(response["default"], settings.default_model)
        self.assertIn(settings.default_model, model_ids)
        for known in KNOWN_MODELS:
            self.assertIn(known, model_ids)

    def test_every_model_has_a_provider(self) -> None:
        response = asyncio.run(list_models())
        for model in response["models"]:
            self.assertIn(model["provider"], {"openai", "claude"})


if __name__ == "__main__":
    unittest.main()

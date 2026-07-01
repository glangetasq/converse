from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.assets import AssetLibrary, TextAsset, fingerprint


class FingerprintTests(unittest.TestCase):
    def test_stable_and_content_sensitive(self) -> None:
        self.assertEqual(fingerprint("hello"), fingerprint("hello"))
        self.assertNotEqual(fingerprint("hello"), fingerprint("hello "))

    def test_asset_fingerprint_tracks_text(self) -> None:
        a = TextAsset(name="prompts/x/judge", version="v1", text="score it")
        self.assertEqual(a.spec(), {"name": "prompts/x/judge", "version": "v1", "fingerprint": a.fingerprint})
        self.assertEqual(a.fingerprint, fingerprint("score it"))


class AsTemplateTests(unittest.TestCase):
    def test_returns_template_and_validates_fields(self) -> None:
        a = TextAsset(name="prompts/x/suggest", version="v1", text="Hi ${name}")
        self.assertEqual(a.as_template().substitute(name="Q"), "Hi Q")
        a.as_template({"name"})  # exact match: no raise

    def test_field_mismatch_raises(self) -> None:
        a = TextAsset(name="prompts/x/suggest", version="v1", text="Hi ${name}")
        with self.assertRaises(ValueError):
            a.as_template({"name", "unused"})


class AssetLibraryTests(unittest.TestCase):
    def test_loads_versioned_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "prompts" / "linkedin" / "suggest").mkdir(parents=True)
            (base / "prompts" / "linkedin" / "suggest" / "v2.md").write_text("draft a reply", encoding="utf-8")
            asset = AssetLibrary(base).load("prompts/linkedin/suggest", "v2")
            self.assertEqual(asset.text, "draft a reply")
            self.assertEqual(asset.version, "v2")
            self.assertEqual(asset.fingerprint, fingerprint("draft a reply"))

    def test_missing_asset_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                AssetLibrary(Path(tmp)).load("scorecards/linkedin", "v9")


if __name__ == "__main__":
    unittest.main()

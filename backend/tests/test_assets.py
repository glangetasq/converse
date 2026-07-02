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


class LatestVersionTests(unittest.TestCase):
    @staticmethod
    def _library(*stems: str) -> AssetLibrary:
        tmp = tempfile.mkdtemp()
        folder = Path(tmp) / "prompts" / "x"
        folder.mkdir(parents=True)
        for stem in stems:
            (folder / f"{stem}.md").write_text("body", encoding="utf-8")
        return AssetLibrary(Path(tmp))

    def test_ranks_by_number_not_lexicographically(self) -> None:
        # "v9" > "v10" as strings, so this catches naive string max
        self.assertEqual(self._library("v1", "v2", "v9", "v10").latest_version("prompts/x"), "v10")

    def test_dotted_versions_rank_below_next_major(self) -> None:
        lib = self._library("v1", "v2", "v2.1", "v2.10")
        self.assertEqual(lib.latest_version("prompts/x"), "v2.10")  # (2,10) > (2,1) > (2,)

    def test_ignores_non_version_files_and_raises_when_none(self) -> None:
        self.assertEqual(self._library("v1", "draft", "notes").latest_version("prompts/x"), "v1")
        with self.assertRaises(FileNotFoundError):
            self._library("draft").latest_version("prompts/x")


if __name__ == "__main__":
    unittest.main()

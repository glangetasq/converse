"""LinkedIn's binding to the shared asset tree (backend/assets). Bump a *_VERSION to
point at a new file; the fingerprint in each spec() moves on its own."""

from __future__ import annotations

from ...assets import ASSETS_DIR, AssetLibrary

LIBRARY = AssetLibrary(ASSETS_DIR)

SUGGEST = "prompts/linkedin/suggest"
JUDGE = "prompts/linkedin/judge"
SCORECARD = "scorecards/linkedin"

SUGGEST_VERSION = "v1"
JUDGE_VERSION = "v1"
SCORECARD_VERSION = "v1"   # must match Scorecard.version

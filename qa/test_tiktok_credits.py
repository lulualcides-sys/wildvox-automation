"""Offline tests: generated TikTok captions must retain all source credits."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from tiktok_credits import attributed_tiktok_caption


class TikTokCreditsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.daily = json.loads((ROOT / "configs" / "daily.json").read_text(encoding="utf-8"))

    def test_current_non_sharealike_candidates_include_all_eight_sources(self):
        for key, entry in self.daily.items():
            if any("by-sa" in str(s.get("license", "")).lower() for s in entry["sources"]):
                with self.assertRaisesRegex(ValueError, "ShareAlike"):
                    attributed_tiktok_caption(entry)
                continue
            result = attributed_tiktok_caption(entry)
            self.assertLessEqual(len(result), 2200, key)
            self.assertTrue(result.startswith(entry["caption"]), key)
            for source in entry["sources"]:
                self.assertIn(source["sourcePage"], result, key)
                self.assertIn(source["license_url"], result, key)
                self.assertIn(source["author"], result, key)

    def test_missing_creator_fails_closed(self):
        entry = copy.deepcopy(next(iter(self.daily.values())))
        entry["sources"][0]["author"] = ""
        with self.assertRaisesRegex(ValueError, "missing creator"):
            attributed_tiktok_caption(entry)

    def test_oversized_caption_fails_not_truncated(self):
        entry = copy.deepcopy(next(iter(self.daily.values())))
        entry["caption"] = "A" * 2200
        with self.assertRaisesRegex(ValueError, "Do not silently truncate"):
            attributed_tiktok_caption(entry)

    def test_duplicate_source_fails(self):
        entry = copy.deepcopy(next(iter(self.daily.values())))
        entry["sources"][1]["url"] = entry["sources"][0]["url"]
        with self.assertRaisesRegex(ValueError, "duplicate footage"):
            attributed_tiktok_caption(entry)


if __name__ == "__main__":
    unittest.main()

"""Offline tests: generated TikTok captions must retain all source credits."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from tiktok_credits import attributed_tiktok_caption
from qa_rendered_batch import caption_credit_errors


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

    def test_rendered_caption_gate_accepts_exact_full_credits(self):
        entry = next(e for e in self.daily.values() if not any(
            "by-sa" in str(s.get("license", "")).lower() for s in e["sources"]))
        meta = {
            "caption": attributed_tiktok_caption(entry),
            "publication_hold": True,
            "attribution_review_required": True,
        }
        self.assertEqual(caption_credit_errors(entry, meta), [])

    def test_rendered_caption_gate_rejects_base_caption_and_missing_holds(self):
        entry = next(e for e in self.daily.values() if not any(
            "by-sa" in str(s.get("license", "")).lower() for s in e["sources"]))
        meta = {"caption": entry["caption"]}
        errors = caption_credit_errors(entry, meta)
        self.assertTrue(any("complete source attribution" in e for e in errors))
        self.assertTrue(any("publication hold" in e for e in errors))
        self.assertTrue(any("attribution review" in e for e in errors))

    def test_rendered_caption_gate_rejects_truncated_credits(self):
        entry = next(e for e in self.daily.values() if not any(
            "by-sa" in str(s.get("license", "")).lower() for s in e["sources"]))
        meta = {
            "caption": attributed_tiktok_caption(entry)[:-12],
            "publication_hold": True,
            "attribution_review_required": True,
        }
        self.assertTrue(any("complete source attribution" in e
                            for e in caption_credit_errors(entry, meta)))

    def test_rendered_caption_gate_rejects_sharealike(self):
        entry = copy.deepcopy(next(iter(self.daily.values())))
        entry["sources"][0]["license"] = "CC BY-SA 4.0"
        errors = caption_credit_errors(entry, {
            "caption": entry["caption"],
            "publication_hold": True,
            "attribution_review_required": True,
        })
        self.assertTrue(any("ShareAlike" in e for e in errors))




if __name__ == "__main__":
    unittest.main()

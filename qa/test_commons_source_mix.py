"""Offline regression tests for per-video Commons source quotas."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_commons_sources import validate_source_mix


def candidate(videos=6, images=2, photo_exception=False, evidence=True):
    entry = {
        "sources": ([{"type": "video"} for _ in range(videos)]
                    + [{"type": "image"} for _ in range(images)])
    }
    if photo_exception:
        entry["trend_exception"] = {"photo_only_allowed": True}
        if evidence:
            entry["trend_exception"].update({
                "evidence_url": "https://example.org/research",
                "evidence_published_date": "2026-10-30",
            })
    return entry


def batch(entry):
    return {f"animal_{i}": candidate(**entry) for i in range(5)}


class CommonsSourceMixTests(unittest.TestCase):
    def test_six_videos_two_photos_each_are_valid(self):
        self.assertEqual(validate_source_mix(batch({"videos": 6, "images": 2})), 30)

    def test_five_videos_three_photos_each_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "6-10 videos"):
            validate_source_mix(batch({"videos": 5, "images": 3}))

    def test_documented_photo_only_exception_is_valid(self):
        entries = batch({"videos": 6, "images": 2})
        entries["animal_0"] = candidate(
            videos=0, images=3, photo_exception=True, evidence=True
        )
        self.assertEqual(validate_source_mix(entries), 24)

    def test_photo_only_requires_evidence(self):
        entries = batch({"videos": 6, "images": 2})
        entries["animal_0"] = candidate(
            videos=0, images=3, photo_exception=True, evidence=False
        )
        with self.assertRaisesRegex(RuntimeError, "published evidence"):
            validate_source_mix(entries)

    def test_photo_only_needs_three_photos(self):
        entries = batch({"videos": 6, "images": 2})
        entries["animal_0"] = candidate(
            videos=0, images=2, photo_exception=True, evidence=True
        )
        with self.assertRaisesRegex(RuntimeError, "3 photos"):
            validate_source_mix(entries)

    def test_unsupported_media_type_is_rejected(self):
        entries = batch({"videos": 6, "images": 2})
        entries["animal_0"]["sources"][0]["type"] = "audio"
        with self.assertRaisesRegex(RuntimeError, "unsupported media type"):
            validate_source_mix(entries)

    def test_actual_daily_batch_keeps_all_forty_video_sources(self):
        daily = json.loads((ROOT / "configs" / "daily.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_source_mix(daily), 40)


if __name__ == "__main__":
    unittest.main()

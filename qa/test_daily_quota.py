"""Monthly WildVox documentary contract, backward compatible with old footage."""
import copy
import json
from pathlib import Path
import unittest

from test_editorial_contract import load_validation

ROOT = Path(__file__).resolve().parents[1]


class MonthlyDocumentaryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.check = staticmethod(load_validation())
        cls.legacy = json.loads(
            (ROOT / "configs/daily.json").read_text(encoding="utf-8")
        )

    def documentary(self):
        candidate = copy.deepcopy(next(iter(self.legacy.values())))
        candidate["revision"] = "2026-11-15-test-longform-v1"
        candidate["min_duration"] = 60
        candidate["max_duration"] = 180
        candidate["target_shot_seconds"] = 15
        candidate["max_shot_seconds"] = 18
        candidate["publication_hold"] = True
        return {"test_documentary": candidate}

    def test_existing_2026_11_14_short_remains_valid_but_not_released(self):
        self.check(copy.deepcopy(self.legacy))
        self.assertTrue(all(v.get("publication_hold") for v in self.legacy.values()))

    def test_new_60_to_180_sec_documentary_accepted(self):
        self.check(self.documentary())

    def test_new_documentary_must_not_be_short(self):
        batch = self.documentary()
        item = next(iter(batch.values()))
        item["min_duration"], item["max_duration"] = 30, 45
        with self.assertRaisesRegex(RuntimeError, "60-240s"):
            self.check(batch)

    def test_documentary_max_duration_hard_limit(self):
        batch = self.documentary()
        next(iter(batch.values()))["max_duration"] = 601
        with self.assertRaisesRegex(RuntimeError, "60-240s"):
            self.check(batch)

    def test_documentary_requires_real_video_not_photo_only(self):
        batch = self.documentary()
        next(iter(batch.values()))["trend_exception"] = {
            "photo_only_allowed": True
        }
        with self.assertRaisesRegex(RuntimeError, "real moving footage"):
            self.check(batch)

    def test_documentary_does_not_exceed_unique_clip_capacity(self):
        batch = self.documentary()
        item = next(iter(batch.values()))
        item["max_duration"] = 220
        item["max_shot_seconds"] = 12
        item["target_shot_seconds"] = 12
        with self.assertRaisesRegex(RuntimeError, "cannot cover"):
            self.check(batch)

    def test_new_documentary_rejects_overlong_unchanging_shots(self):
        batch = self.documentary()
        item = next(iter(batch.values()))
        item["max_shot_seconds"] = 25
        with self.assertRaisesRegex(RuntimeError, "at most 20"):
            self.check(batch)


if __name__ == "__main__":
    unittest.main()

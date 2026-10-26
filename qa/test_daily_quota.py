"""Editorial regression: five fresh 30-45s TikTok videos, no long-form entries."""
import copy
import json
from pathlib import Path
import unittest
from test_editorial_contract import load_validation

ROOT = Path(__file__).resolve().parents[1]

class DailyQuotaContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.check = staticmethod(load_validation())
        cls.data = json.loads((ROOT / "configs/daily.json").read_text(encoding="utf-8"))

    def test_five_short_videos_pass(self):
        self.assertEqual(len(self.data), 5)
        self.assertTrue(all(
            v["min_duration"] == 30 and v["max_duration"] == 45
            for v in self.data.values()
        ))
        self.check(copy.deepcopy(self.data))

    def test_long_form_regression_rejected(self):
        data = copy.deepcopy(self.data)
        entry = next(iter(data.values()))
        entry["min_duration"] = 60
        entry["max_duration"] = 75
        entry["min_unique_videos"] = 8
        with self.assertRaisesRegex(RuntimeError, "30-45s"):
            self.check(data)

if __name__ == "__main__":
    unittest.main()

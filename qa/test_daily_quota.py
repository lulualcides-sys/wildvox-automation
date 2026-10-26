"""Editorial regression: reject legacy five-short quota and wrong 3:2 mix."""
import copy
import json
from pathlib import Path
import unittest
from test_editorial_contract import load_validation

ROOT=Path(__file__).resolve().parents[1]
class DailyQuotaContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.check=staticmethod(load_validation())
        cls.data=json.loads((ROOT/"configs/daily.json").read_text(encoding="utf-8"))

    def test_three_short_two_long_pass(self):
        self.assertEqual(sum(v["min_duration"]==30 for v in self.data.values()),3)
        self.assertEqual(sum(v["min_duration"]==60 for v in self.data.values()),2)
        self.check(copy.deepcopy(self.data))

    def test_five_short_regression_rejected(self):
        data=copy.deepcopy(self.data)
        for entry in data.values():
            entry["min_duration"]=30
            entry["max_duration"]=45
            entry["min_unique_videos"]=6
        with self.assertRaisesRegex(RuntimeError,"3 short"):
            self.check(data)

if __name__=="__main__":
    unittest.main()

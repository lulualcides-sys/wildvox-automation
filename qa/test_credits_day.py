"""Offline regression tests for Commons credits audit editorial date."""
import ast
import re
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_commons_credits.py"


def load_day_function():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef)
               and node.name == "editorial_day_from_batch"]
    if len(matches) != 1:
        raise AssertionError("Missing production editorial-day validator")
    namespace = {"re": re}
    exec(compile(ast.Module(body=matches, type_ignores=[]), str(SCRIPT), "exec"), namespace)
    return namespace["editorial_day_from_batch"]


class CreditsDayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.extract = staticmethod(load_day_function())

    def batch(self, dates):
        return {f"animal_{index}": {"revision": f"{day}-animal_{index}-v1"}
                for index, day in enumerate(dates)}

    def test_current_day_from_all_five_revisions(self):
        self.assertEqual(self.extract(self.batch(["2026-10-30"] * 5)), "2026-10-30")

    def test_reject_mixed_dates(self):
        with self.assertRaisesRegex(ValueError, "Mixed editorial dates"):
            self.extract(self.batch(["2026-10-30"] * 4 + ["2026-10-29"]))

    def test_reject_undated_revision(self):
        batch = self.batch(["2026-10-30"] * 5)
        batch["animal_0"]["revision"] = "old-undated"
        with self.assertRaisesRegex(ValueError, "Missing dated revision"):
            self.extract(batch)

    def test_reject_wrong_count(self):
        for n in (0, 6):
            with self.subTest(n=n), self.assertRaisesRegex(ValueError, "Expected 1 to 5 candidates"):
                self.extract(self.batch(["2026-10-30"] * n))

    def test_one_to_five_today_revisions(self):
        for n in range(1, 6):
            with self.subTest(n=n):
                self.assertEqual(self.extract(self.batch(["2026-11-12"] * n)), "2026-11-12")


if __name__ == "__main__":
    unittest.main()

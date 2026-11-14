"""Test real monthly quota logic without posting or calling Metricool."""
import importlib.util
from datetime import date
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts" / "metricool_monthly_calendar.py"
spec = importlib.util.spec_from_file_location("metricool_monthly_calendar", PATH)
calendar_plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calendar_plan)


class MonthlyPublishingContract(unittest.TestCase):
    def test_every_month_has_exactly_20_nonduplicate_dates(self):
        for month in range(1, 13):
            dates = calendar_plan.publication_days(2027, month)
            self.assertEqual(len(dates), 20)
            self.assertEqual(len(set(dates)), 20)
            self.assertEqual(dates, sorted(dates))
            self.assertTrue(all(1 <= d <= 31 for d in dates))

    def test_february_leap_and_february_regular(self):
        for year in (2027, 2028):
            dates = calendar_plan.publication_days(year, 2)
            self.assertEqual(len(set(dates)), 20)
            self.assertLessEqual(max(dates), 29 if year == 2028 else 28)

    def test_only_planned_dates_can_trigger_slot(self):
        target = date(2027, 5, 1)
        self.assertTrue(calendar_plan.is_planned_day(target))
        all_days = [d for d in range(1, 32)
                    if calendar_plan.is_planned_day(date(2027, 5, d))]
        self.assertEqual(len(all_days), 20)

    def test_actual_and_scheduled_posts_reduce_remaining_capacity(self):
        self.assertEqual(calendar_plan.remaining_budget(12, 7), 1)
        self.assertEqual(calendar_plan.remaining_budget(20, 0), 0)
        self.assertEqual(calendar_plan.remaining_budget(19, 3), 0)

    def test_bad_provider_counts_fail_closed(self):
        for values in ((-1, 0), (2, -1), (None, 1), ("3", 2)):
            with self.assertRaises(ValueError):
                calendar_plan.remaining_budget(*values)


if __name__ == "__main__":
    unittest.main()

"""Buffer stock summary used by the daily routine (read-only)."""
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import buffer_stock as bs  # noqa: E402
import buffer_post_single as bps  # noqa: E402
from publish_buffer import TZ  # noqa: E402


def post(day, hm, status="scheduled"):
    h, m = hm
    dt = datetime(2026, 11, day, h, m, tzinfo=TZ)
    return {"status": status, "dueAt": dt.astimezone().isoformat()}


class Stock(unittest.TestCase):
    now = datetime(2026, 11, 23, 9, 0, tzinfo=TZ)

    def test_empty_queue_needs_videos_today(self):
        s = bs.stock_summary([], self.now)
        self.assertEqual(s, {"scheduled": 0, "queue_free": 10, "first_gap": "2026-11-23", "days_ahead": 0})

    def test_three_full_days(self):
        posts = [post(d, hm) for d in (23, 24, 25, 26) for hm in ((12, 40), (19, 35))]
        posts.append(post(22, (19, 35), "sent"))
        s = bs.stock_summary(posts, self.now)
        self.assertEqual(s["scheduled"], 8)
        self.assertEqual(s["queue_free"], 2)
        self.assertEqual(s["first_gap"], "2026-11-27")
        self.assertEqual(s["days_ahead"], 3)

    def test_half_day_is_a_gap(self):
        posts = [post(23, (12, 40)), post(23, (19, 35)), post(24, (12, 40))]
        self.assertEqual(bs.stock_summary(posts, self.now)["first_gap"], "2026-11-24")

    def test_next_slot_can_look_further_ahead(self):
        used = {datetime(2026, 11, 23 + d, h, m, tzinfo=TZ) for d in range(3) for h, m in ((12, 40), (19, 35))}
        with self.assertRaises(RuntimeError):
            bps.next_slot(self.now, used, [(12, 40), (19, 35)])
        self.assertEqual(bps.next_slot(self.now, used, [(12, 40), (19, 35)], days=8).day, 26)


if __name__ == "__main__":
    unittest.main()

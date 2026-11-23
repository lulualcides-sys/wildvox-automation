#!/usr/bin/env python3
"""Read-only: how many WildVox posts are already scheduled ahead on Buffer.

Prints one line `STOCK {...}` for the daily routine:
  scheduled   future scheduled posts on the TikTok channel
  queue_free  room left in the Buffer Free queue (10 pending posts)
  first_gap   first day from today with fewer than 2 posts (needs videos)
  days_ahead  full days (2 posts) covered from tomorrow before the first gap
Never creates, edits or deletes posts.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_buffer as pb  # noqa: E402

PER_DAY = 2


def stock_summary(posts, now):
    today = now.date()
    future = [p for p in posts if p.get("status") == "scheduled" and p.get("dueAt")
              and pb.utc_datetime(p["dueAt"]).astimezone(pb.TZ) > now]
    per_day = {}
    for p in posts:
        if p.get("dueAt") and p.get("status") in ("scheduled", "sent"):
            d = pb.utc_datetime(p["dueAt"]).astimezone(pb.TZ).date()
            per_day[d] = per_day.get(d, 0) + 1
    gap = today
    while per_day.get(gap, 0) >= PER_DAY:
        gap += timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    return {"scheduled": len(future), "queue_free": max(0, pb.MAX_PENDING_FREE - len(future)),
            "first_gap": gap.isoformat(), "days_ahead": max(0, (gap - tomorrow).days)}


def main():
    from buffer_post_single import find_channel
    org, ch = find_channel(sys.argv[1] if len(sys.argv) > 1 else "wildvox")
    print("STOCK " + json.dumps(stock_summary(pb.read_existing_posts(org, ch), datetime.now(pb.TZ))))


if __name__ == "__main__":
    main()

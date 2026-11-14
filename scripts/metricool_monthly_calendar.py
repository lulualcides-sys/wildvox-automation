#!/usr/bin/env python3
"""Zero-cost 20-per-calendar-month publishing schedule for @wildvox.

This is a local schedule generator, not a Metricool quota confirmation. Actual
posts already published on Metricool must be counted before sending any post.
"""
import argparse
import calendar
import json
from datetime import date


def publication_days(year, month, limit=20):
    length = calendar.monthrange(year, month)[1]
    if not 1 <= limit <= length:
        raise ValueError("Invalid monthly quota")
    # Deterministically spread exactly twenty unique dates over each month.
    return [(i * length) // limit + 1 for i in range(limit)]


def is_planned_day(today, limit=20):
    return today.day in publication_days(today.year, today.month, limit)


def remaining_budget(already_published, already_scheduled, limit=20):
    """Fail closed: both kinds of posts count against planned monthly slots."""
    if not isinstance(already_published, int) or not isinstance(already_scheduled, int):
        raise ValueError("Quota inputs must be integers from provider data")
    if already_published < 0 or already_scheduled < 0:
        raise ValueError("Negative provider counts are not valid")
    return max(0, limit - already_published - already_scheduled)


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("--date", default=date.today().isoformat())
    arg.add_argument("--check-day", action="store_true")
    args = arg.parse_args()
    today = date.fromisoformat(args.date)
    result = {
        "month": today.strftime("%Y-%m"),
        "max_actual_published_posts": 20,
        "planned_days": publication_days(today.year, today.month),
        "planned_today": is_planned_day(today),
        "metricool_usage_verified": False,
        "safe_to_publish": False,
    }
    print(json.dumps(result, ensure_ascii=False))
    if args.check_day and not result["planned_today"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

"""Validate tomorrow's narrated-story arc without invalidating today's batch.

The production renderer already synchronizes its shot changes with visual_plan
spoken blocks.  This test guards editorial intent; it does not claim that
animated arrows, diagrams or zooms are implemented.
"""
import json
import re
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVATION = date(2026, 10, 27)
ALLOWED = {"hook", "setup", "action", "explanation", "twist", "payoff"}


def validate_narrative_arc(entry):
    plan = entry.get("visual_plan")
    if not isinstance(plan, list) or not 5 <= len(plan) <= 7:
        raise ValueError("narrative visual_plan must have 5-7 blocks")
    roles = [str(block.get("story_role", "")).strip().lower()
             for block in plan]
    if any(role not in ALLOWED for role in roles):
        raise ValueError("every story_role must be explicitly valid")
    if roles[0] != "hook" or roles[-1] != "payoff":
        raise ValueError("narrative requires first hook and final payoff")
    if "action" not in roles[1:-1]:
        raise ValueError("narrative requires an action block")
    if not {"explanation", "twist"}.intersection(roles[1:-1]):
        raise ValueError("narrative requires an explanation or twist")


def is_active_revision(value):
    match = re.match(r"^([0-9]{4}-[0-9]{2}-[0-9]{2})(?:-|$)", str(value or ""))
    return bool(match and date.fromisoformat(match.group(1)) >= ACTIVATION)


class NarrativeStoryContract(unittest.TestCase):
    def test_future_daily_uses_narrative_arc(self):
        daily = json.loads((ROOT / "configs/daily.json").read_text(encoding="utf-8"))
        active = [(key, cfg) for key, cfg in daily.items()
                  if is_active_revision(cfg.get("revision"))]
        # Today (2026-10-26) was prepared before the storytelling transition.
        if not active:
            return
        self.assertEqual(len(active), 5, "all five future videos must follow narrative style")
        for key, cfg in active:
            with self.subTest(key=key):
                validate_narrative_arc(cfg)

    def test_valid_story_arc(self):
        item = {"visual_plan": [{"story_role": role} for role in
                ("hook", "setup", "action", "explanation", "payoff")]}
        validate_narrative_arc(item)

    def test_missing_action_rejected(self):
        item = {"visual_plan": [{"story_role": role} for role in
                ("hook", "setup", "setup", "explanation", "payoff")]}
        with self.assertRaisesRegex(ValueError, "action"):
            validate_narrative_arc(item)

    def test_missing_payoff_rejected(self):
        item = {"visual_plan": [{"story_role": role} for role in
                ("hook", "setup", "action", "explanation", "setup")]}
        with self.assertRaisesRegex(ValueError, "payoff"):
            validate_narrative_arc(item)


if __name__ == "__main__":
    unittest.main()

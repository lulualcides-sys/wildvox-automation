"""Unit safety tests for the Publer GitHub-Issue handoff. No network calls."""
import importlib.util
import pathlib
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("publer_handoff", ROOT / "scripts/publer_handoff.py")
handoff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handoff)
TZ = ZoneInfo("America/Sao_Paulo")


class PublerHandoffTest(unittest.TestCase):
    def now(self):
        return datetime(2026, 11, 14, 9, 0, tzinfo=TZ)

    def test_next_slot_observes_future_buffer(self):
        self.assertEqual(handoff.next_slot(self.now()).strftime("%H:%M"), "10:05")
        t = datetime(2026, 11, 14, 9, 40, tzinfo=TZ)
        self.assertEqual(handoff.next_slot(t).strftime("%H:%M"), "12:40")
        self.assertIsNone(handoff.next_slot(datetime(2026, 11, 14, 22, 0, tzinfo=TZ)))

    def test_stale_research_is_not_reused(self):
        with self.assertRaisesRegex(RuntimeError, "current-day"):
            handoff.prepare("cat_nov12",
                            {"cat_nov12": {"revision": "2026-11-12-old"}},
                            pathlib.Path("."), pathlib.Path("."), self.now())

    def test_invalid_key_fails_before_disk_access(self):
        with self.assertRaisesRegex(RuntimeError, "Invalid candidate"):
            handoff.prepare("../secrets", {}, pathlib.Path("."), pathlib.Path("."), self.now())

    def test_editorial_hash_canonical(self):
        self.assertEqual(handoff.config_fingerprint({"a": 1, "b": 2}),
                         handoff.config_fingerprint({"b": 2, "a": 1}))

    def test_receipt_requires_independent_visual_quality_approval(self):
        entry = {"revision": "2026-11-14-cat"}
        meta = {"config_sha256": "config"}
        checks = {
            "curiosity_first": True,
            "verified_biological_mechanism": True,
            "comparison_or_consequence": True,
            "non_descriptive_story": True,
            "independent_original_zip_inspection": "Inspected original ZIP, MP4, previews and sources",
        }
        receipt = {
            "day_local": "2026-11-14",
            "candidate_key": "cat",
            "revision": entry["revision"],
            "decision": "APPROVE",
            "publication_hold": True,
            "network": "tiktok",
            "account": "@wildvox",
            "config_sha256": "config",
            "media_sha256": "sha256",
            "git_blob_mp4": "blob",
            "github_actions_run_id": 1,
            "github_original_zip_artifact_id": 2,
            "editorial_checks": checks,
        }
        validate = lambda: handoff.valid_receipt(
            receipt, "cat", entry, meta, "sha256", "blob", self.now())
        self.assertFalse(validate())
        checks["visual_quality_approved"] = True
        self.assertTrue(validate())
        receipt["media_sha256"] = "different"
        self.assertFalse(validate())
        receipt["media_sha256"] = "sha256"
        receipt["account"] = "@wildvox6"
        self.assertFalse(validate())

    def test_issue_idempotence_catches_closed_and_open(self):
        issue = {"title": "https://raw.githubusercontent.com/org/repo/media/cat.mp4",
                 "body": "Full credited caption"}
        with patch.object(handoff, "github",
                          return_value=[{"title": issue["title"]}]) as g:
            with self.assertRaisesRegex(RuntimeError, "Duplicate Publer"):
                handoff.create_handoff(issue, "dummy")
            self.assertEqual(g.call_count, 1)

    def test_issue_fields_map_to_one_step_zap(self):
        issue = {"title": "https://raw.githubusercontent.com/org/repo/media/cat.mp4",
                 "body": "Full credited caption"}
        with patch.object(handoff, "github",
                          side_effect=[[], {"number": 31}]) as g:
            self.assertEqual(handoff.create_handoff(issue, "dummy"), {"number": 31})
            payload = g.call_args.args[3]
            self.assertEqual(payload["title"], issue["title"])
            self.assertEqual(payload["body"], issue["body"])
            self.assertEqual(payload["labels"], ["wildvox-publer-ready"])


if __name__ == "__main__":
    unittest.main()

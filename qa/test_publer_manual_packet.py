"""Regression safety tests for zero-cost Publer manual handoff."""
import importlib.util
from datetime import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("publer_manual_packet", SCRIPTS / "publer_manual_packet.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
NOW = datetime(2026, 11, 14, 12, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))


class PublerManualTest(unittest.TestCase):
    def test_stale_is_never_handed_off(self):
        ok, held = p.build({"cat": {"revision": "2026-11-12-cat"}},
                           Path("."), Path("."), NOW, check=lambda _: None)
        self.assertFalse(ok)
        self.assertEqual(len(held), 1)

    def test_missing_approval_is_blocked(self):
        with patch.object(p, "prepare", side_effect=RuntimeError("No approved receipt")):
            ok, held = p.build({"cat": {"revision": "2026-11-14-cat"}},
                               Path("."), Path("."), NOW, check=lambda _: None)
        self.assertFalse(ok)
        self.assertEqual(len(held), 1)

    def test_exact_approved_caption_and_url_survive(self):
        packet = {"key": "cat", "title": "https://example.org/cat.mp4",
                  "body": "Texto em portugues e creditos completos",
                  "sha256": "a" * 64, "next_slot": "2026-11-14T16:10:00-03:00"}
        with patch.object(p, "prepare", return_value=packet):
            ok, held = p.build({"cat": {"revision": "2026-11-14-cat"}},
                               Path("."), Path("."), NOW, check=lambda _: None)
        self.assertEqual(held, [])
        rendered = p.report(ok, held, NOW)
        self.assertIn(packet["title"], rendered)
        self.assertIn(packet["body"], rendered)
        self.assertIn(packet["sha256"], rendered)
        self.assertIn("NAO confirma", rendered)

    def test_missing_public_mp4_fails_closed(self):
        with patch.object(p, "prepare", return_value={"title": "https://example.org/no.mp4"}):
            def fail(_):
                raise RuntimeError("HTTP 404")
            ok, held = p.build({"cat": {"revision": "2026-11-14-cat"}},
                               Path("."), Path("."), NOW, check=fail)
        self.assertFalse(ok)
        self.assertEqual(len(held), 1)

    def test_more_than_five_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Too many"):
            p.build({str(i): {} for i in range(6)},
                    Path("."), Path("."), NOW)

    def test_missing_explicit_key_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Unknown candidate"):
            p.build({}, Path("."), Path("."), NOW, selected="ghost")

    def test_empty_report_has_no_media_links(self):
        summary = p.report([], [], NOW)
        self.assertIn("Nenhum video NOVO", summary)
        self.assertNotIn("https://raw.githubusercontent.com/", summary)


if __name__ == "__main__":
    unittest.main()

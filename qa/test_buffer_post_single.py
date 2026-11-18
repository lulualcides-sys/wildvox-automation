"""Single approved Buffer post: credits only used sources, safe slots."""
import importlib.util
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("buffer_post_single", ROOT / "scripts" / "buffer_post_single.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

KEY = "gatos_piscar_lento_comunicacao_nov14"
AMELIA = "https://commons.wikimedia.org/wiki/File:Amelia_-cat_purrs_and_kneads.webm"


class BufferPostSingle(unittest.TestCase):
    def entry(self):
        return json.loads((ROOT / "configs" / "daily.json").read_text(encoding="utf-8"))[KEY]

    def test_credits_exclude_unused_source(self):
        text = mod.credited_caption(self.entry(), [AMELIA])
        self.assertNotIn(AMELIA, text)
        self.assertIn("7. ", text)
        self.assertNotIn("8. ", text)
        self.assertLessEqual(len(text), 2200)

    def test_rejects_sharealike(self):
        e = self.entry()
        e["sources"][1]["license"] = "CC BY-SA 4.0"
        with self.assertRaises(ValueError):
            mod.credited_caption(e)

    def test_next_slot_skips_past_and_used(self):
        tz = mod.pb.TZ
        now = datetime(2026, 11, 18, 11, 10, tzinfo=tz)
        self.assertEqual(mod.next_slot(now, set()).strftime("%H:%M"), "12:40")
        used = {datetime(2026, 11, 18, 12, 40, tzinfo=tz)}
        self.assertEqual(mod.next_slot(now, used).strftime("%H:%M"), "16:10")

    def test_refuses_non_media_branch_url(self):
        with self.assertRaises(RuntimeError):
            mod.main(["--key", KEY, "--media-url", "https://example.com/x.mp4"])


if __name__ == "__main__":
    unittest.main()

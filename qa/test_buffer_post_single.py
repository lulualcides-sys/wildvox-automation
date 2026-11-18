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

    def test_long_credit_list_is_compacted_not_truncated(self):
        src = {"author": "Autor Muito Comprido da Silva", "license": "CC BY 4.0",
               "license_url": "https://creativecommons.org/licenses/by/4.0/", "type": "video"}
        e = {"caption": "x " * 300, "sources": [dict(src,
              assetTitle=f"Um titulo de arquivo bem longo numero {i} gravado em 4K.webm",
              sourcePage=f"https://commons.wikimedia.org/wiki/File:Um_titulo_de_arquivo_bem_longo_numero_{i}_gravado_em_4K_com_mais_texto.webm",
              url=f"https://commons.wikimedia.org/wiki/Special:FilePath/Um_titulo_{i}_" + "y" * 80 + ".webm")
              for i in range(12)]}
        text = mod.credited_caption(e)
        self.assertLessEqual(len(text), 2200)
        self.assertIn("12. Autor Muito Comprido da Silva", text)
        self.assertEqual(text.count("https://creativecommons.org/licenses/by/4.0/"), 1)

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
            mod.main(["--key", KEY, "--tiktok-handle", "wildvox6", "--media-url", "https://example.com/x.mp4"])


    def test_channel_match_is_exact(self):
        chans = [{"id": "a", "name": "wildvox66", "externalLink": "https://tiktok.com/@wildvox66", "service": "tiktok",
                  "isQueuePaused": False, "isDisconnected": False, "isLocked": False},
                 {"id": "b", "name": "wildvox6", "externalLink": "https://tiktok.com/@wildvox6", "service": "tiktok",
                  "isQueuePaused": False, "isDisconnected": False, "isLocked": False}]
        def fake(q, v=None):
            return {"account": {"organizations": [{"id": "o"}]}} if "account" in q else {"channels": chans}
        orig = mod.pb.graphql
        mod.pb.graphql = fake
        try:
            self.assertEqual(mod.find_channel("@wildvox6"), ("o", "b"))
            with self.assertRaises(RuntimeError):
                mod.find_channel("wildvox")
        finally:
            mod.pb.graphql = orig


if __name__ == "__main__":
    unittest.main()

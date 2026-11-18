"""Daily MPT batch: source picking, clip timing, batch posting order."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


pick = load("mpt_pick_sources")
render = load("mpt_offline_render")
batch = load("buffer_post_batch")


def cand(title, w=1920, h=1080):
    return {"title": title, "sourcePage": "https://commons.wikimedia.org/wiki/File:" + title.replace(" ", "_"),
            "url": "https://upload.wikimedia.org/x/" + title.replace(" ", "_"), "author": "A",
            "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "width": w, "height": h}


class DailyBatch(unittest.TestCase):
    def test_choose_skips_used_portrait_and_low_res(self):
        pool = [cand(f"cat {i}.webm") for i in range(10)] + [cand("tall.webm", 1080, 1920), cand("small.webm", 960, 540)]
        used = {"cat 0.webm", "file:cat 1.webm"}
        picks = pick.choose(pool, used, 12)
        titles = {p["assetTitle"] for p in picks}
        self.assertEqual(len(picks), 8)
        self.assertNotIn("cat 0.webm", titles)
        self.assertNotIn("cat 1.webm", titles)
        self.assertNotIn("tall.webm", titles)
        self.assertNotIn("small.webm", titles)
        self.assertTrue(all(p["url"].startswith("https://commons.wikimedia.org/wiki/Special:FilePath/") for p in picks))

    def test_no_footage_shared_between_videos_of_the_day(self):
        pool = [cand(f"fox {i}.webm") for i in range(14)]
        def gather(kind, arg):
            return pool if kind == "verify" else [c["title"] for c in pool]
        b = {"a": {"commons_categories": ["Category:X"]}, "b": {"commons_categories": ["Category:X"]}}
        out, dropped = pick.pick_batch(b, set(), gather)
        self.assertIn("a", out)
        self.assertIn("b", dropped)  # only 2 left for b -> fail closed, no reuse
        self.assertEqual(len(out["a"]["sources"]), 12)

    def test_picked_sources_pass_render_validation(self):
        pool = [cand(f"owl {i}.webm") for i in range(8)]
        out, _ = pick.pick_batch({"k": {"script": "Fato.", "curiosity_fact_sheet": {"x": 1},
                                        "commons_categories": ["C"]}},
                                 set(), lambda k, a: pool if k == "verify" else ["t"])
        self.assertEqual(len(render.validate_candidate(out["k"])), 8)

    def test_clip_seconds_spreads_footage(self):
        self.assertEqual(render.clip_seconds(36.8, 7), 6)
        self.assertEqual(render.clip_seconds(90, 12), 8)
        self.assertEqual(render.clip_seconds(10, 12), 3)
        self.assertEqual(render.clip_seconds(400, 6), 15)

    def test_load_metas_keeps_batch_order_and_skips_failed(self):
        with tempfile.TemporaryDirectory() as d:
            for k in ("b", "a"):
                (Path(d) / f"{k}.json").write_text(json.dumps({"key": k, "caption": "c", "sources": [],
                    "media_url": batch.MEDIA_PREFIX + k + ".mp4"}))
            metas = batch.load_metas(Path(d), ["a", "missing", "b"])
            self.assertEqual([m["key"] for m in metas], ["a", "b"])

    def test_load_metas_rejects_foreign_media(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.json").write_text(json.dumps({"key": "a", "media_url": "https://evil/x.mp4"}))
            with self.assertRaises(RuntimeError):
                batch.load_metas(Path(d), ["a"])


if __name__ == "__main__":
    unittest.main()

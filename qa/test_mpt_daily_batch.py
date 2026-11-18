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

    def test_junk_titles_and_free_text_search_are_ignored(self):
        bad = ["2023 Neo QLED 8K- More Wow than Ever (Full Version) - Samsung.webm", "OpenAI - This is Sora 2.webm",
               "The Mystery of the Malties Woodchuck - Rugrats - NickRewind.webm", "COMO COCER PULPO - HOW TO COOK.webm",
               "Hummingbird Moth feeding at 25% speed.webm", "Le Déjeuner des Minet (1906).webm",
               "Octopus-shaped rotating neon light.webm"]
        pool = [cand(t) for t in bad] + [cand(f"good cat {i}.webm") for i in range(6)]
        picks = pick.choose(pool, set(), 12)
        self.assertEqual({p["assetTitle"] for p in picks}, {f"good cat {i}.webm" for i in range(6)})
        calls = []
        def gather(kind, arg):
            calls.append(kind)
            return pool if kind == "verify" else ["t"]
        pick.pick_batch({"k": {"commons_categories": ["C"], "commons_search": ["cat"]}}, set(), gather)
        self.assertNotIn("search", calls)

    def test_batch_poster_requires_review_approval(self):
        with tempfile.TemporaryDirectory() as d:
            b = Path(d) / "b.json"
            b.write_text(json.dumps({"a": {}}))
            import io, contextlib
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                batch.main(["--batch", str(b), "--meta-dir", d, "--tiktok-handle", "x",
                            "--approved", str(Path(d) / "missing.json")])
            self.assertIn("AWAITING_REVIEW", out.getvalue())

    def test_pixabay_hits_filtered_by_tags_and_quality(self):
        def hit(i, tags, w=1920, h=1080, typ="film", dur=10):
            return {"id": i, "tags": tags, "type": typ, "duration": dur, "user": "u", "pageURL": f"https://pixabay.com/videos/x-{i}/",
                    "videos": {"large": {"url": f"https://cdn.pixabay.com/video/{i}_large.mp4", "width": w, "height": h}}}
        hits = [hit(1, "cat, kitten, pet"), hit(2, "dog, pet"), hit(3, "cat, cartoon"), hit(4, "cat", typ="animation"),
                hit(5, "cat", w=1080, h=1920), hit(6, "cat", dur=2), hit(7, "kitten, animal")]
        got = pick.pixabay_candidates(hits, ["cat", "kitten"])
        self.assertEqual([c["title"] for c in got], ["pixabay-1.mp4", "pixabay-7.mp4"])
        src = pick.to_source(got[0])
        self.assertTrue(render.is_pixabay(src))

    def test_pixabay_batch_passes_render_validation_and_short_caption(self):
        hits = [{"id": i, "tags": "cat", "type": "film", "duration": 12, "user": "u",
                 "pageURL": f"https://pixabay.com/videos/cat-{i}/",
                 "videos": {"large": {"url": f"https://cdn.pixabay.com/video/{i}.mp4", "width": 1920, "height": 1080}}}
                for i in range(9)]
        out, dropped = pick.pick_batch({"k": {"script": "Fato.", "curiosity_fact_sheet": {"x": 1},
                                               "pixabay_queries": ["cat"], "pixabay_required_tags": ["cat"]}},
                                       set(), lambda kind, a: hits)
        self.assertEqual(dropped, {})
        self.assertEqual(len(render.validate_candidate(out["k"])), 9)
        import buffer_post_single as bps
        cap = bps.credited_caption({"caption": "Texto #WildVox", "sources": out["k"]["sources"]})
        self.assertIn("Pixabay", cap)
        self.assertLess(len(cap), 300)

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

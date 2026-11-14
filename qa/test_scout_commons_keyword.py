"""Daily source discovery must be safe, cheap and never auto-approve."""
import importlib.util
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "scout_commons_keyword", ROOT / "scripts/scout_commons_keyword.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CommonsKeywordSearchTests(unittest.TestCase):
    def test_cirrus_search_only_files_namespace_and_filters_titles(self):
        calls = []
        def fake(params):
            calls.append(params)
            return {"query": {"search": [
                {"title": "File:Real-cat.webm"},
                {"title": "File:Real-cat.webm"},
                {"title": "Category:Not-a-file"},
                {"title": "File:Kitten.webm"},
            ]}}
        titles, counts = module.search_titles(
            queries=("cat filetype:video",), per_query=50, query_fn=fake)
        self.assertEqual(titles, ["File:Kitten.webm", "File:Real-cat.webm"])
        self.assertEqual(calls[0]["srnamespace"], "6")
        self.assertEqual(calls[0]["list"], "search")
        self.assertEqual(counts["cat filetype:video"], 2)

    def test_query_budget_guard(self):
        with self.assertRaises(ValueError):
            module.search_titles(per_query=501)
        with self.assertRaises(ValueError):
            module.search_titles(queries=("a","b","c","d","e","f"))

    def test_no_claims_of_approved_footage(self):
        with tempfile.TemporaryDirectory() as d:
            def fake(_):
                return {"query": {"search": [{"title": "File:Cat.webm"}]}}
            def verifier(titles, used, include_crop_review):
                self.assertTrue(include_crop_review)
                self.assertEqual(titles, ["File:Cat.webm"])
                return [{
                    "title": "Cat.webm", "crop_review_required": True,
                    "source_status": "RESEARCH_ONLY_REQUIRES_VISUAL_CROP_REVIEW"
                }]
            result = module.run(d, query_fn=fake, verifier=verifier)
            self.assertEqual(result["ready_to_render"], False)
            self.assertEqual(result["visual_independent_approval"], False)
            self.assertEqual(result["new_crop_review_only_sources"], 1)

    def test_rate_limit_produces_explicit_block(self):
        with tempfile.TemporaryDirectory() as d:
            def fail(_):
                raise module.CommonsRateLimited("HTTP 429")
            result = module.run(d, query_fn=fail)
            self.assertEqual(result["status"], "BLOCKED_EXTERNAL_COMMONS_HTTP_429")
            self.assertEqual(result["candidates"], [])
            self.assertFalse(result["ready_to_render"])

    def test_original_broll_selector_prioritizes_new_cat_sources(self):
        from preview_commons_crops import selected
        known = {
            "title": "Amelia -cat purrs and kneads.webm",
            "url": "https://upload.wikimedia.org/wikipedia/commons/amelia.webm",
            "sourcePage": "https://commons.wikimedia.org/wiki/File:amelia.webm",
            "source_status": "RESEARCH_ONLY_NOT_VISUALLY_APPROVED",
            "file_size": 1_000_000,
        }
        new = {**known, "title": "Cat eye closeup fresh.webm",
               "url": "https://upload.wikimedia.org/wikipedia/commons/fresh.webm"}
        result = selected([known, new], auto_select=True)
        self.assertEqual(result[0]["title"], new["title"])

    def test_invalid_video_host_not_selected(self):
        from preview_commons_crops import selected
        fake = {"title":"cat face.webm",
                "url":"https://untrusted.example/cat.webm",
                "sourcePage":"https://commons.wikimedia.org/wiki/File:cat.webm",
                "source_status":"RESEARCH_ONLY_NOT_VISUALLY_APPROVED"}
        self.assertEqual(selected([fake], auto_select=True), [])


if __name__ == "__main__":
    unittest.main()

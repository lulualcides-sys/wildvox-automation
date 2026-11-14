"""Research-only Wikimedia licensing and no-repeat regression suite."""
import importlib.util
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "scout_commons_portrait", ROOT / "scripts/scout_commons_portrait.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def page(title="File:Unused-cat.webm", license_="CC BY 4.0",
         width=1080, height=1920, mime="video/webm", author="Example author"):
    return {
        "title": title,
        "imageinfo": [{
            "mime": mime, "width": width, "height": height,
            "url": "https://upload.wikimedia.org/wikipedia/commons/unused-cat.webm",
            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Unused-cat.webm",
            "size": 1000000,
            "extmetadata": {
                "LicenseShortName": {"value": license_},
                "Artist": {"value": author},
                "LicenseUrl": {"value": "https://creativecommons.org/licenses/by/4.0/"},
            },
        }]
    }


class CommonsScoutTest(unittest.TestCase):
    def test_real_cc_by_portrait_candidate_is_research_only(self):
        result = mod.source_candidate(page(), set())
        self.assertEqual(result["license"], "CC BY 4.0")
        self.assertEqual(result["foreground_fraction"], 1)
        self.assertEqual(result["source_status"], "RESEARCH_ONLY_NOT_VISUALLY_APPROVED")

    def test_reject_licensed_sharealike(self):
        self.assertIsNone(mod.source_candidate(page(license_="CC BY-SA 4.0"), set()))

    def test_reject_unreviewed_landscape_filler(self):
        self.assertIsNone(mod.source_candidate(page(width=1920, height=1080), set()))

    def test_reject_images_and_unknown_license(self):
        self.assertIsNone(mod.source_candidate(page(mime="image/jpeg"), set()))
        self.assertIsNone(mod.source_candidate(page(license_="Pixabay License"), set()))

    def test_reject_missing_author(self):
        self.assertIsNone(mod.source_candidate(page(author=""), set()))

    def test_reject_previously_used_same_original_filename(self):
        self.assertIsNone(mod.source_candidate(page(), {"unused-cat.webm"}))

    def test_normalize_special_filepath_and_original(self):
        self.assertEqual(
            mod.canonical_source("https://commons.wikimedia.org/wiki/Special:FilePath/Cat%20Video.webm"),
            mod.canonical_source("https://upload.wikimedia.org/wikipedia/commons/3/37/Cat_Video.webm"),
        )

    def test_reject_license_with_missing_attribution_link(self):
        original = page()
        original["imageinfo"][0]["extmetadata"]["LicenseUrl"]["value"] = ""
        self.assertIsNone(mod.source_candidate(original, set()))

    def test_used_source_history_from_prior_media_branch(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "old_meta.json"
            p.write_text(json.dumps({"sources": [{"url":
                "https://commons.wikimedia.org/wiki/Special:FilePath/Cat%20Video.webm"}]}))
            self.assertIn("cat video.webm", mod.previously_used(pathlib.Path(d)))


if __name__ == "__main__":
    unittest.main()

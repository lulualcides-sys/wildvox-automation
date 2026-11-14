"""No fabricated review footage: preview selection remains unapproved."""
import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "preview_commons_crops", ROOT / "scripts/preview_commons_crops.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class RealFootageReviewTest(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("PIL"), "Pillow optional outside preview workflow")
    def test_center_crop_is_9_16_preview_only(self):
        from PIL import Image
        input_image = Image.new("RGB", (1920, 1080), "orange")
        crop = mod.centered_portrait(input_image)
        self.assertEqual(crop.size, (608, 1080))
        self.assertEqual(input_image.size, (1920, 1080))

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "Pillow optional outside preview workflow")
    def test_native_portrait_preserved(self):
        from PIL import Image
        frame = Image.new("RGB", (720, 1280), "red")
        self.assertEqual(mod.centered_portrait(frame).size, frame.size)

    def test_license_candidates_only_and_never_automatic_approval(self):
        sample = [{"title": mod.PREFERRED[0],
                   "url": "https://upload.wikimedia.org/wikipedia/commons/cat.webm",
                   "sourcePage": "https://commons.wikimedia.org/wiki/File:cat.webm",
                   "source_status": "RESEARCH_ONLY_REQUIRES_VISUAL_CROP_REVIEW",
                   "crop_review_required": True, "file_size": 3200}]
        result = mod.selected(sample)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["crop_review_required"])
        sample[0]["source_status"] = "PUBLISHED"
        self.assertEqual(mod.selected(sample), [])

    def test_uses_only_real_licensed_commons_transcodes(self):
        rows = [
            {"src": "https://upload.wikimedia.org/x/test.webm",
             "transcodekey": "240p.vp9.webm"},
            {"src": "https://upload.wikimedia.org/x/quality.webm",
             "transcodekey": "480p.vp9.webm"},
            {"src": "https://fake-cdn.example/hd.webm",
             "transcodekey": "480p.vp9.webm"},
        ]
        url, key = mod.choose_transcode(rows)
        self.assertTrue(url.endswith("quality.webm"))
        self.assertEqual(key, "480p.vp9.webm")

    def test_noncommons_or_nonvideo_derivative_rejected(self):
        url, key = mod.choose_transcode([
            {"src": "https://fake.example/x.webm", "transcodekey": "480p.vp9.webm"},
            {"src": "https://upload.wikimedia.org/x/image.jpg", "transcodekey": "480p.jpg"},
        ])
        self.assertIsNone(url)
        self.assertIsNone(key)

    def test_host_restriction(self):
        sample = [{"title": mod.PREFERRED[0],
                   "url": "https://example.org/pretend.webm",
                   "sourcePage": "https://commons.wikimedia.org/wiki/File:cat.webm",
                   "source_status": "RESEARCH_ONLY_NOT_VISUALLY_APPROVED",
                   "file_size": 3000}]
        self.assertFalse(mod.selected(sample))


if __name__ == "__main__":
    unittest.main()

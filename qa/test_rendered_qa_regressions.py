"""Regression checks for rendered-video QA; never substitute for visual approval."""
import importlib.util
import pathlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

MODULE = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "qa_rendered_batch.py"
spec = importlib.util.spec_from_file_location("wildvox_technical_qa", MODULE)
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


class FreezeTailRegression(unittest.TestCase):
    def read_freezes(self, stderr, duration):
        fake = SimpleNamespace(stderr=stderr, stdout="", returncode=0)
        with patch.object(qa.subprocess, "run", return_value=fake):
            return qa.freeze_durations(pathlib.Path("candidate.mp4"), duration)

    def test_frozen_last_frames_are_counted_even_without_freeze_end(self):
        result = self.read_freezes(
            "[freezedetect] lavfi.freezedetect.freeze_start: 36.6\n", 38.8)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0], 2.2, places=3)

    def test_closed_freeze_not_double_counted(self):
        result = self.read_freezes(
            "[freezedetect] lavfi.freezedetect.freeze_start: 18.2\n"
            "[freezedetect] lavfi.freezedetect.freeze_end: 19.4 | "
            "lavfi.freezedetect.freeze_duration: 1.2\n", 38.8)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0], 1.2, places=3)

    def test_no_freezes(self):
        self.assertEqual(self.read_freezes("", 35.0), [])

    def test_ended_freeze_and_trailing_freeze(self):
        result = self.read_freezes(
            "lavfi.freezedetect.freeze_start: 4.0\n"
            "lavfi.freezedetect.freeze_end: 5.1 | lavfi.freezedetect.freeze_duration: 1.1\n"
            "lavfi.freezedetect.freeze_start: 33.2\n", 35.0)
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[1], 1.8, places=3)


class RenderProvenanceRegression(unittest.TestCase):
    def test_config_fingerprint_is_stable_across_json_key_order(self):
        first = {"script": "A", "sources": [{"url": "x", "start_seconds": 2}],
                 "visual_plan": [{"text": "A", "tags": ["a"]}]}
        second = {"visual_plan": [{"tags": ["a"], "text": "A"}],
                  "sources": [{"start_seconds": 2, "url": "x"}], "script": "A"}
        self.assertEqual(qa.config_fingerprint(first), qa.config_fingerprint(second))

    def test_config_fingerprint_rejects_visual_and_render_changes(self):
        base = {"script": "A", "visual_plan": [{"text": "A", "scene": "Closeup",
                "tags": ["beak"], "overlay_label": "FEED"}], "max_shot_seconds": 8}
        for field, value in (("scene", "Wide"), ("tags", ["generic"]),
                             ("overlay_label", "OTHER")):
            changed = {"script": "A", "visual_plan": [dict(base["visual_plan"][0])],
                       "max_shot_seconds": 8}
            changed["visual_plan"][0][field] = value
            self.assertNotEqual(qa.config_fingerprint(base), qa.config_fingerprint(changed))
        changed = dict(base, max_shot_seconds=12)
        self.assertNotEqual(qa.config_fingerprint(base), qa.config_fingerprint(changed))

    def test_reject_stale_source_pool(self):
        config = [{"url": "https://example.org/new.mp4"}]
        rendered = [{"url": "https://example.org/old.mp4"}]
        self.assertFalse(qa.sources_match(config, rendered))

    def test_accept_exact_source_pool(self):
        sources = [{"url": "https://example.org/one.mp4"},
                   {"url": "https://example.org/two.mp4"}]
        self.assertTrue(qa.sources_match(sources, sources))

    def test_reject_same_url_with_changed_seek(self):
        config = [{"url": "https://example.org/clip.mp4", "start_seconds": 24}]
        rendered = [{"url": "https://example.org/clip.mp4", "start_seconds": 3}]
        self.assertFalse(qa.sources_match(config, rendered))

    def test_reject_same_url_with_changed_tags(self):
        config = [{"url": "https://example.org/clip.mp4", "tags": ["actual_behavior"]}]
        rendered = [{"url": "https://example.org/clip.mp4", "tags": ["generic_hook"]}]
        self.assertFalse(qa.sources_match(config, rendered))

    def test_accept_independent_identical_source_metadata(self):
        config = [{"url": "https://example.org/clip.mp4", "start_seconds": 24,
                   "tags": ["action"], "license": "CC BY 4.0"}]
        rendered = [dict(config[0])]
        self.assertTrue(qa.sources_match(config, rendered))


if __name__ == "__main__":
    unittest.main()

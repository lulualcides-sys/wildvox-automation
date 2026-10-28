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
    def test_reject_stale_source_pool(self):
        config = [{"url": "https://example.org/new.mp4"}]
        rendered = [{"url": "https://example.org/old.mp4"}]
        self.assertFalse(qa.sources_match(config, rendered))

    def test_accept_exact_source_pool(self):
        sources = [{"url": "https://example.org/one.mp4"},
                   {"url": "https://example.org/two.mp4"}]
        self.assertTrue(qa.sources_match(sources, sources))


if __name__ == "__main__":
    unittest.main()

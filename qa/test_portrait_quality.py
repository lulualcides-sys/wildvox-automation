"""Portrait QA regressions: genuine foreground must occupy the vertical frame."""
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import portrait_quality as framing


class PortraitQualityGate(unittest.TestCase):
    def test_unreviewed_landscape_is_rejected(self):
        with patch.object(framing, "probe_dimensions", return_value=(1920, 1080)):
            with self.assertRaisesRegex(RuntimeError, "Unapproved blurred portrait filler"):
                framing.require_reviewed_portrait("cat.webm", {})

    def test_uncropped_vertical_video_passes(self):
        with patch.object(framing, "probe_dimensions", return_value=(720, 1280)):
            self.assertAlmostEqual(framing.require_reviewed_portrait("cat.webm", {}), 1.0)

    def test_reviewed_916_crop_passes_without_automatic_motion(self):
        with patch.object(framing, "probe_dimensions", return_value=(1920, 1080)):
            self.assertEqual(framing.require_reviewed_portrait(
                "cat.webm", {"portrait_crop": "9:16"}), 1)

    def test_four_five_still_exposes_too_much_blur(self):
        with patch.object(framing, "probe_dimensions", return_value=(1920, 1080)):
            with self.assertRaisesRegex(RuntimeError, "sharp foreground 70%"):
                framing.require_reviewed_portrait(
                    "cat.webm", {"portrait_crop": "4:5"})

    def test_narrow_unreviewed_video_is_rejected(self):
        with patch.object(framing, "probe_dimensions", return_value=(450, 1280)):
            with self.assertRaisesRegex(RuntimeError, "Unapproved blurred portrait filler"):
                framing.require_reviewed_portrait("cat.webm", {})

    def test_invalid_dimensions_and_crop_rejected(self):
        with self.assertRaises(ValueError):
            framing.foreground_fraction(0, 100)
        with self.assertRaises(ValueError):
            framing.foreground_fraction(500, 1000, "invalid")


if __name__ == "__main__":
    unittest.main()

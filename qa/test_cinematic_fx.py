"""Regression + actual FFmpeg/libass smoke for animated WildVox overlays."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cinematic_fx as fx


def sample_timeline():
    return [
        {
            "start": 0.0, "end": 3.1, "story_role": "hook",
            "overlay_label": "THE IMPOSSIBLE SHOT",
            "fx": [
                {"type": "arrow", "from": [.17, .56], "to": [.7, .42]},
                {"type": "ring", "center": [.7, .42], "radius": .055}
            ]
        },
        {
            "start": 3.1, "end": 5.6, "story_role": "payoff",
            "overlay_label": "TARGET HIT",
            "fx": [{"type": "box", "center": [.5, .48], "width": .22, "height": .1}]
        }
    ]


class CinematicFXContract(unittest.TestCase):
    def test_old_batch_does_not_change(self):
        self.assertEqual(fx.build_events([{"start": 0, "end": 2}]), [])
        self.assertEqual(fx.camera_filter("fps=30", 2, None), "fps=30")

    def test_reviewed_coordinates_make_timed_arrow_ring_box(self):
        events = fx.build_events(sample_timeline())
        self.assertGreaterEqual(len(events), 5)
        self.assertTrue(any("\\p1" in item for item in events))
        self.assertTrue(any("THE IMPOSSIBLE SHOT" in item for item in events))
        self.assertTrue(any("\\fad(" in item for item in events))

    def test_untrusted_caption_does_not_inject_ass(self):
        event = fx.label(r"{\pos(1,1)}TEST", 85, 900, 0, 2)
        self.assertNotIn(r"{\pos(1,1)}", event)
        self.assertIn("TEST", event)

    def test_invalid_or_unsafe_annotation_fails_closed(self):
        a = sample_timeline()
        a[0]["fx"][0]["to"] = [1.2, .4]
        with self.assertRaisesRegex(ValueError, "safe video area"):
            fx.build_events(a)
        a = sample_timeline()
        a[0]["fx"][0]["to"] = a[0]["fx"][0]["from"]
        with self.assertRaisesRegex(ValueError, "too short"):
            fx.build_events(a)

    def test_camera_filter_never_adds_synthetic_motion(self):
        for role in (None, "hook", "setup", "action", "payoff"):
            camera = fx.camera_filter("fps=30", 2, role)
            self.assertEqual(camera, "fps=30")
            self.assertNotIn("zoompan", camera)

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg unavailable")
    def test_real_unmodified_camera_filter_ffmpeg(self):
        filt = fx.camera_filter("fps=30", .2, "hook")
        p = subprocess.run([
            "ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel",
            "error", "-f", "lavfi", "-i",
            "color=c=0x253647:s=1080x1920:r=30:d=0.2",
            "-vf", filt, "-frames:v", "5", "-f", "null", "-"
        ], capture_output=True, text=True, timeout=45)
        self.assertEqual(p.returncode, 0, p.stderr[-1500:])

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg unavailable")
    def test_real_libass_render_overlay(self):
        # Uses a cheap synthetic frame; no external video, model or network.
        with tempfile.TemporaryDirectory() as work:
            base = Path(work)
            track = base / "fx.ass"
            track.write_text(
                "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\n"
                "PlayResY: 1920\n\n[V4+ Styles]\n"
                "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
                "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,"
                "ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
                "Alignment,MarginL,MarginR,MarginV,Encoding\n"
                "Style: Default,DejaVu Sans,46,&H00FFFFFF,&H00FFFFFF,"
                "&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,"
                "20,20,40,1\n\n[Events]\n"
                "Format: Layer,Start,End,Style,Name,MarginL,MarginR,"
                "MarginV,Effect,Text\n", encoding="utf-8"
            )
            self.assertTrue(fx.enrich_subtitles(track, sample_timeline()))
            result = subprocess.run([
                "ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel",
                "error", "-f", "lavfi", "-i",
                "color=c=0x243846:s=540x960:r=15:d=0.5",
                "-vf", "ass=" + str(track), "-frames:v", "5",
                "-f", "null", "-"
            ], capture_output=True, text=True, timeout=35)
            self.assertEqual(result.returncode, 0, result.stderr[-1500:])


if __name__ == "__main__":
    unittest.main()

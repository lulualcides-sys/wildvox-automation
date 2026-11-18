"""MoneyPrinterTurbo offline render (Actions): never publish, never paid APIs."""
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts" / "mpt_offline_render.py"
spec = importlib.util.spec_from_file_location("mpt_offline_render", FILE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

EXAMPLE = """[app]
video_source = "pexels"
subtitle_provider = "edge"
upload_post_enabled = true
upload_post_api_key = "leaked"
upload_post_username = "someone"
upload_post_auto_upload = true
[whisper]
model_size = "large-v3"
"""


class MptOfflineRender(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mpt = Path(self.tmp.name) / "mpt"
        self.mpt.mkdir()
        (self.mpt / "cli.py").write_text("# stub\n")
        (self.mpt / "config.example.toml").write_text(EXAMPLE)

    def test_config_forces_cross_posting_off(self):
        text = mod.write_safe_config(self.mpt).read_text()
        self.assertIn("upload_post_enabled = false", text)
        self.assertIn('upload_post_api_key = ""', text)
        self.assertIn("upload_post_auto_upload = false", text)
        self.assertNotIn("leaked", text)
        self.assertIn('video_source = "local"', text)
        self.assertIn('subtitle_provider = "whisper"', text)

    def test_config_rejects_unknown_layout(self):
        (self.mpt / "config.example.toml").write_text("[app]\n")
        with self.assertRaises(RuntimeError):
            mod.write_safe_config(self.mpt)

    def test_render_command_is_local_and_unpaid(self):
        shots = [self.mpt / f"s{i}.mp4" for i in range(8)]
        cmd = mod.build_render_command(self.mpt, "Roteiro aprovado.", shots, self.mpt / "v.wav")
        joined = " ".join(map(str, cmd))
        self.assertIn("--video-source local", joined)
        self.assertIn("--custom-audio-file", joined)
        self.assertIn("--bgm-type none", joined)
        self.assertIn("--stop-at video", joined)
        self.assertNotIn("--confirm-", joined)  # no paid provider confirmations

    def test_render_style_no_zoom_centred_brand_font(self):
        shots = [self.mpt / f"s{i}.mp4" for i in range(8)]
        cmd = mod.build_render_command(self.mpt, "x", shots, self.mpt / "v.wav")
        opt = lambda k: cmd[cmd.index(k) + 1]
        self.assertEqual(opt("--video-fit-mode"), "contain")
        self.assertEqual(opt("--subtitle-position"), "custom")
        self.assertTrue(70 <= float(opt("--custom-position")) <= 80)
        self.assertEqual(opt("--font-name"), "Inter-Black.ttf")

    def test_captions_sit_in_bottom_black_bar_with_brand_colours(self):
        shots = [self.mpt / f"s{i}.mp4" for i in range(8)]
        cmd = mod.build_render_command(self.mpt, "x", shots, self.mpt / "v.wav")
        opt = lambda k: cmd[cmd.index(k) + 1]
        # 16:9 video centred in 1080x1920 ends at y=1264; a caption box of
        # 120-260 px must start below it and stay above the TikTok UI (~1650).
        for box in (120, 260):
            top = (1920 - box) * float(opt("--custom-position")) / 100
            self.assertGreater(top, 1264)
            self.assertLess(top + box, 1650)
        self.assertEqual(opt("--text-fore-color"), "#FFFFFF")
        self.assertEqual(opt("--subtitle-background-color"), "#FF4D22")
        self.assertIn("--rounded-subtitle-background", cmd)

    def test_only_widescreen_shots_keep_captions_off_the_image(self):
        self.assertTrue(mod.is_widescreen(1920, 1080))
        self.assertTrue(mod.is_widescreen(3840, 2160))
        self.assertFalse(mod.is_widescreen(640, 640))
        self.assertFalse(mod.is_widescreen(1080, 1920))

    def test_logo_overlay_top_right(self):
        cmd = mod.logo_overlay_command(Path("in.mp4"), Path("logo.png"), Path("out.mp4"))
        joined = " ".join(map(str, cmd))
        self.assertIn("overlay=W-w-", joined)
        self.assertIn("-c:a copy", joined)
        self.assertEqual(str(cmd[-1]), "out.mp4")

    def test_render_command_rejects_duplicates_and_few_shots(self):
        one = self.mpt / "s.mp4"
        with self.assertRaises(ValueError):
            mod.build_render_command(self.mpt, "x", [one] * 8, self.mpt / "v.wav")
        with self.assertRaises(ValueError):
            mod.build_render_command(self.mpt, "x", [one], self.mpt / "v.wav")

    def test_candidate_requires_fact_sheet_and_commons(self):
        good = {
            "script": "Fato verificado.",
            "curiosity_fact_sheet": {"facts": ["x"]},
            "sources": [{
                "url": f"https://commons.wikimedia.org/wiki/Special:FilePath/c{i}.webm",
                "sourcePage": f"https://commons.wikimedia.org/wiki/File:c{i}.webm",
                "license": "CC BY 3.0", "type": "video"} for i in range(8)],
        }
        self.assertEqual(len(mod.validate_candidate(good)), 8)
        bad = dict(good, curiosity_fact_sheet=None)
        with self.assertRaises(ValueError):
            mod.validate_candidate(bad)
        bad = dict(good, sources=[dict(good["sources"][0], sourcePage="https://pexels.com/x")] * 8)
        with self.assertRaises(ValueError):
            mod.validate_candidate(bad)

    def test_not_wired_to_production(self):
        daily = (ROOT / ".github" / "workflows" / "wildvox-daily.yml").read_text()
        self.assertNotIn("mpt_offline_render", daily)


if __name__ == "__main__":
    unittest.main()

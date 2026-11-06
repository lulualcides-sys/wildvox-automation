"""MoneyPrinterTurbo integration: local-only, no paid or publish stages."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "scripts" / "moneyprinterturbo_pilot.py"
spec = importlib.util.spec_from_file_location("mpt_pilot", FILE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class MoneyPrinterTurboPilot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.assets = self.base / "licensed_assets"
        self.assets.mkdir()
        self.mpt = self.base / "MoneyPrinterTurbo"
        self.mpt.mkdir()
        (self.mpt / "cli.py").write_text("print('stub: no media conversion')\n")
        self.plan = {
            "script": "Why cats leap with such accuracy. Here is how they do it.",
            "narration_file": "michael.wav",
            "sources": []
        }
        (self.assets / "michael.wav").write_bytes(b"local-test-fixture")
        for i in range(8):
            path = f"shot_{i}.mp4"
            (self.assets / path).write_bytes(b"fixture")
            self.plan["sources"].append({
                "file": path, "source_page": f"https://commons.wikimedia.org/wiki/File:shot_{i}.mp4",
                "license": "CC BY-SA 4.0", "reviewed": True
            })

    def build(self):
        return mod.build_command(self.plan, self.assets, self.mpt)

    def test_only_local_media_original_voice_and_no_crossposting(self):
        cmd = self.build()
        self.assertEqual(cmd[cmd.index("--stop-at") + 1], "materials")
        self.assertEqual(cmd[cmd.index("--video-source") + 1], "local")
        self.assertEqual(cmd[cmd.index("--video-aspect") + 1], "9:16")
        self.assertIn("--custom-audio-file", cmd)
        self.assertIn("--no-subtitle-enabled", cmd)
        self.assertIn("none", cmd)
        self.assertNotIn("--video-count", cmd)
        self.assertNotIn("--confirm-wavespeed-charge", cmd)

    def test_default_cli_does_not_execute_external_renderer(self):
        manifest = self.base / "plan.json"
        manifest.write_text(json.dumps(self.plan))
        p = subprocess.run([
            sys.executable, str(FILE), "--plan", str(manifest),
            "--assets-root", str(self.assets), "--mpt-root", str(self.mpt)
        ], capture_output=True, text=True, check=True)
        value = json.loads(p.stdout)
        self.assertEqual(value["stage"], "materials")
        self.assertFalse(value["publish"])
        self.assertNotIn("stub: no media conversion", p.stdout)

    def test_rejects_missing_review_or_license(self):
        self.plan["sources"][2]["reviewed"] = False
        with self.assertRaisesRegex(ValueError, "visual review"):
            self.build()
        self.plan["sources"][2]["reviewed"] = True
        self.plan["sources"][2]["license"] = ""
        with self.assertRaisesRegex(ValueError, "license"):
            self.build()

    def test_rejects_remote_and_duplicate_sources(self):
        self.plan["sources"][0]["source_page"] = "https://example.com/video"
        with self.assertRaisesRegex(ValueError, "Wikimedia"):
            self.build()
        self.plan["sources"][0]["source_page"] = "https://commons.wikimedia.org/wiki/File:shot_0.mp4"
        self.plan["sources"][1]["file"] = "shot_0.mp4"
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.build()

    def test_rejects_path_escape_and_incorrect_shot_count(self):
        self.plan["sources"][0]["file"] = "../outside.mp4"
        with self.assertRaisesRegex(ValueError, "inside"):
            self.build()
        self.plan["sources"][0]["file"] = "shot_0.mp4"
        self.plan["sources"] = self.plan["sources"][:7]
        with self.assertRaisesRegex(ValueError, "8-12"):
            self.build()


if __name__ == "__main__":
    unittest.main()

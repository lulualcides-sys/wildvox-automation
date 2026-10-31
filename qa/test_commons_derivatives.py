"""Offline tests: failed Commons originals may use the same video's real transcode."""
import ast
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from commons_derivatives import get_fallback_video_urls


def load_safe_download(fake_run, fallback):
    path = ROOT / "scripts" / "generate_video.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == "safe_download")
    scope = {"run": fake_run, "subprocess": subprocess, "get_fallback_video_urls": fallback}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), scope)
    return scope["safe_download"]


class CommonsDerivativeFallbackTests(unittest.TestCase):
    def test_only_authentic_commons_video_derivatives(self):
        payload = {"query": {"pages": [{"videoinfo": [{"derivatives": [
            {"src": "//upload.wikimedia.org/wikipedia/commons/transcoded/960.webm", "width": 960, "height": 540},
            {"src": "https://evil.example/960.webm", "width": 960, "height": 540},
            {"src": "https://upload.wikimedia.org/wikipedia/commons/transcoded/640.webm", "width": 640, "height": 360},
            {"src": "https://upload.wikimedia.org/wikipedia/commons/transcoded/still.jpg", "width": 960, "height": 540},
        ]}] }]}}
        with patch("commons_derivatives.urlopen", return_value=io.BytesIO(json.dumps(payload).encode())) as mocked:
            urls = get_fallback_video_urls("https://commons.wikimedia.org/wiki/Special:FilePath/Goats%20eating.webm")
        self.assertEqual(len(urls), 2)
        self.assertTrue(urls[0].endswith("/960.webm"))
        self.assertTrue(urls[1].endswith("/640.webm"))
        self.assertIn("File%3AGoats+eating.webm", mocked.call_args.args[0].full_url)

    def test_rejects_untrusted_or_nonvideo_original_without_api_call(self):
        with patch("commons_derivatives.urlopen") as mocked:
            self.assertEqual(get_fallback_video_urls("https://example.org/Goats.webm"), [])
            self.assertEqual(get_fallback_video_urls("https://commons.wikimedia.org/wiki/Special:FilePath/still.jpg"), [])
            mocked.assert_not_called()

    def test_original_failure_then_same_footage_derivative_succeeds(self):
        urls = []
        derivative = "https://upload.wikimedia.org/wikipedia/commons/transcoded/960.webm"
        def fake_run(cmd):
            urls.append(cmd[-1])
            if len(urls) == 1:
                raise subprocess.CalledProcessError(22, cmd)
            Path(cmd[cmd.index("-o") + 1]).write_bytes(b"x" * 120001)
        download = load_safe_download(fake_run, lambda url: [derivative])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.mp4"
            self.assertTrue(download("https://commons.wikimedia.org/wiki/Special:FilePath/Goats.webm", path))
            self.assertGreater(path.stat().st_size, 100000)
        self.assertEqual(urls, ["https://commons.wikimedia.org/wiki/Special:FilePath/Goats.webm", derivative])

    def test_noncommons_failure_never_uses_unrelated_footage(self):
        urls = []
        def fail(cmd):
            urls.append(cmd[-1])
            raise subprocess.CalledProcessError(22, cmd)
        download = load_safe_download(fail, lambda url: [])
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(download("https://other.example/clip.mp4", Path(folder) / "clip.mp4"))
        self.assertEqual(urls, ["https://other.example/clip.mp4"])


if __name__ == "__main__":
    unittest.main()

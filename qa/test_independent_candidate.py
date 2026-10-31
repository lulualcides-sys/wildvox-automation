"""One failed WildVox candidate must not block another candidate's technical QA."""
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "wildvox_candidate_qa", ROOT / "scripts" / "qa_rendered_batch.py")
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


class IndependentCandidateQA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "configs" / "daily.json").read_text("utf-8"))
        cls.key = next(iter(cls.config))
        cls.day = str(cls.config[cls.key]["revision"])[:10]

    def make_candidate(self, directory, cfg, key):
        (directory / (key + ".mp4")).write_bytes(b"candidate")
        (directory / (key + "_review.jpg")).write_bytes(b"review")
        blocks = cfg["visual_plan"]
        frame = 34.0 / len(blocks)
        timeline = [{"text": block["text"], "start": i * frame,
                     "end": (i + 1) * frame}
                    for i, block in enumerate(blocks)]
        meta = {
            "key": key, "title": cfg["title"], "duration": 34.0,
            "sources": cfg["sources"],
            "config_sha256": qa.config_fingerprint(cfg),
            "caption": "Test credited caption",
            "publication_hold": True,
            "attribution_review_required": True,
            "narration_timeline": timeline,
        }
        (directory / (key + "_meta.json")).write_text(json.dumps(meta), "utf-8")

    def fake_probe(self, path):
        return {"format": {"duration": "34"}, "streams": [
            {"codec_type": "video", "width": 1080, "height": 1920},
            {"codec_type": "audio"}]}

    def test_one_valid_candidate_passes_with_four_missing_artifacts(self):
        with tempfile.TemporaryDirectory() as root:
            directory = pathlib.Path(root)
            self.make_candidate(directory, self.config[self.key], self.key)
            with patch.object(qa, "probe", side_effect=self.fake_probe), \
                 patch.object(qa, "freeze_durations", return_value=[]), \
                 patch.object(qa, "attributed_tiktok_caption",
                              return_value="Test credited caption"):
                one = qa.inspect(self.config, directory, self.day, self.key)
                whole = qa.inspect(self.config, directory, self.day)
            self.assertTrue(one["technical_pass"], one["errors"])
            self.assertEqual(one["scope"], self.key)
            self.assertEqual(len(one["videos"]), 1)
            self.assertFalse(whole["technical_pass"])
            self.assertEqual(len(whole["videos"]), 5)
            self.assertFalse(one["editorial_approved"])
            self.assertTrue(one["publication_hold"])

    def test_cross_video_duplicate_source_still_rejected(self):
        config = json.loads(json.dumps(self.config))
        other_key = list(config)[1]
        config[other_key]["sources"][0]["url"] = config[self.key]["sources"][0]["url"]
        with tempfile.TemporaryDirectory() as root:
            report = qa.inspect(config, pathlib.Path(root), self.day, self.key)
        self.assertFalse(report["technical_pass"])
        self.assertTrue(any("Duplicate/missing URL" in e for e in report["errors"]))

    def test_unknown_candidate_fails_closed(self):
        report = qa.inspect(self.config, pathlib.Path("/nonexistent"),
                            self.day, "nonexistent-candidate")
        self.assertFalse(report["technical_pass"])
        self.assertIn("Unknown video key", report["errors"][0])


class WorkflowIsolationContract(unittest.TestCase):
    def test_publish_each_candidate_and_keep_editorial_hold(self):
        workflow = (ROOT / ".github" / "workflows" / "wildvox-daily.yml").read_text("utf-8")
        publish = workflow.split("  publish-media:", 1)[1].split("  technical-qa:", 1)[0]
        self.assertIn("max-parallel: 1", publish)
        self.assertIn("needs: [prepare, render]", publish)
        self.assertIn("matrix.animal", publish)
        self.assertIn("--key", publish)
        self.assertIn("daily-${{ matrix.animal }}", publish)
        self.assertNotIn("needs: [render, technical-qa]", publish)
        self.assertNotIn("publication_hold=false", publish)


if __name__ == "__main__":
    unittest.main()

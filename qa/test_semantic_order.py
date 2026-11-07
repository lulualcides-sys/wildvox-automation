"""Regression: match genuine source footage in narration order, not reverse order."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from semantic_shots import plan_semantic_shots


class SemanticMatchingOrderTest(unittest.TestCase):
    def test_shared_tag_two_clip_blocks_preserve_config_order(self):
        tags = ["hook", "setup", "action", "action", "explanation",
                "explanation", "twist", "payoff"]
        local = [
            (f"/unused/source_{i:02}.webm", "video",
             {"tags": [tag], "_duration": 20.0, "_source_index": i})
            for i, tag in enumerate(tags)
        ]
        blocks = [
            {"duration": duration, "tags": [tag]}
            for duration, tag in zip([4, 4, 8, 8, 4, 4],
                                     ["hook", "setup", "action", "explanation",
                                      "twist", "payoff"])
        ]
        schedule = plan_semantic_shots(local, blocks, 8, 1, "regression")
        indices = [shot[0][2]["_source_index"] for shot in schedule]
        self.assertEqual(indices, list(range(8)))
        self.assertTrue(all(seconds <= 8 for _, seconds, _ in schedule))

    def test_ambiguous_hook_and_payoff_choose_declared_order(self):
        tags = ["shared", "setup", "action", "action", "explanation",
                "explanation", "twist", "shared"]
        local = [
            (f"/unused/source_{i:02}.webm", "video",
             {"tags": [tag], "_duration": 20.0, "_source_index": i})
            for i, tag in enumerate(tags)
        ]
        blocks = [
            {"duration": duration, "tags": [tag]}
            for duration, tag in zip([4, 4, 8, 8, 4, 4],
                                     ["shared", "setup", "action", "explanation",
                                      "twist", "shared"])
        ]
        schedule = plan_semantic_shots(local, blocks, 8, 1, "ambiguous")
        indices = [shot[0][2]["_source_index"] for shot in schedule]
        self.assertEqual(indices, list(range(8)))


if __name__ == "__main__":
    unittest.main()

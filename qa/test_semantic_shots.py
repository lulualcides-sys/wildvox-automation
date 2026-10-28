"""Regression tests for Kokoro block-based visual scheduling."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from semantic_shots import plan_semantic_shots


def asset(index, tags, seconds=6.0):
    return (f"clip_{index}.mp4", "video", {
        "tags": tags, "_duration": seconds, "_source_index": index
    })


def block(tag, seconds):
    return {"tags": [tag], "duration": seconds, "scene": tag}


class SemanticShotTests(unittest.TestCase):
    def test_splits_long_block_across_short_relevant_clips(self):
        blocks = [block("a", 12)] + [block(x, 5) for x in "bcdef"]
        local = [asset(0, ["a"], 6), asset(1, ["a"], 6),
                 asset(2, ["a"], 6)] + [
                     asset(i + 3, [tag], 5) for i, tag in enumerate("bcdef")
                 ]
        result = plan_semantic_shots(local, blocks, 8, 0, "long")
        self.assertEqual(len(result), 8)
        self.assertAlmostEqual(sum(shot[1] for shot in result), 37)
        self.assertTrue(all(shot[1] <= 8 for shot in result))
        self.assertEqual(len(set(shot[0][0] for shot in result)), 8)
        self.assertTrue(all(
            set(shot[0][2]["tags"]) & set(shot[2]["tags"]) for shot in result
        ))

    def test_short_source_can_be_used_when_block_is_split(self):
        blocks = [block(x, 6) for x in "abcdef"]
        local = [asset(0, ["a"], 3), asset(1, ["a"], 3),
                 asset(2, ["b"], 3), asset(3, ["b"], 3)] + [
                     asset(i + 4, [tag], 6) for i, tag in enumerate("cdef")
                 ]
        result = plan_semantic_shots(local, blocks, 8, 0, "short")
        self.assertEqual(len(result), 8)
        self.assertTrue(all(shot[1] <= shot[0][2]["_duration"] for shot in result))

    def test_reject_unmatched_semantic_block(self):
        blocks = [block(x, 5) for x in "abcdef"]
        local = [asset(i, ["a"], 7) for i in range(8)]
        with self.assertRaisesRegex(RuntimeError, "cannot match"):
            plan_semantic_shots(local, blocks, 8, 0, "mismatch")

    def test_reject_insufficient_source_duration(self):
        blocks = [block(x, 6) for x in "abcdef"]
        local = [asset(i, ["abcdef"[min(i, 5)]], 1.0) for i in range(8)]
        with self.assertRaisesRegex(RuntimeError, "cannot match"):
            plan_semantic_shots(local, blocks, 8, 0, "too_short")

    def test_reject_more_than_eight_seconds_per_shot(self):
        blocks = [block("a", 20)] + [block(x, 5) for x in "bcdef"]
        local = [asset(i, ["a"], 8) for i in range(3)] + [
            asset(i + 3, [tag], 5) for i, tag in enumerate("bcdef")
        ]
        result = plan_semantic_shots(local, blocks, 8, 0, "twenty")
        self.assertTrue(all(shot[1] <= 8 for shot in result))


if __name__ == "__main__":
    unittest.main()

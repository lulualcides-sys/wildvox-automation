"""Regression tests for Kokoro block-based visual scheduling."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from semantic_shots import plan_semantic_shots, validate_editorial_tags


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


    def test_numbered_key_prefix_tags_are_rejected_before_render(self):
        key = "european_mantis_two_jobs"
        batch = {key: {
            "visual_plan": [{"tags": ["european_mant_1"]}],
            "sources": [{"tags": ["european_mant_1"]}],
        }}
        with self.assertRaisesRegex(ValueError, "numbered placeholder"):
            validate_editorial_tags(batch)

    def test_descriptive_tags_match_sources_and_blocks(self):
        key = "european_mantis_two_jobs"
        batch = {key: {
            "visual_plan": [
                {"tags": ["mantis_raising_raptorial_forelegs"]},
                {"tags": ["mantis_gripping_prey"]},
            ],
            "sources": [
                {"tags": ["mantis_raising_raptorial_forelegs"]},
                {"tags": ["mantis_gripping_prey"]},
            ],
        }}
        self.assertTrue(validate_editorial_tags(batch))

    def test_reject_unassigned_source_tags(self):
        batch = {"kingfisher_nest": {
            "visual_plan": [{"tags": ["kingfisher_excavating_bank"]}],
            "sources": [{"tags": ["kingfisher_eating_fish"]}],
        }}
        with self.assertRaisesRegex(ValueError, "no tagged source"):
            validate_editorial_tags(batch)

    def test_reject_two_blocks_depending_on_one_source(self):
        batch = {"kingfisher_nest": {
            "visual_plan": [
                {"tags": ["kingfisher_digging_bank"]},
                {"tags": ["kingfisher_entering_tunnel"]},
                {"tags": ["kingfisher_carrying_fish"]},
            ],
            "sources": [
                {"tags": ["kingfisher_digging_bank", "kingfisher_entering_tunnel"]},
                {"tags": ["kingfisher_carrying_fish"]},
                {"tags": ["kingfisher_carrying_fish"]},
            ],
        }}
        with self.assertRaisesRegex(ValueError, "distinct source"):
            validate_editorial_tags(batch)

    def test_accept_shared_tags_when_distinct_assignment_exists(self):
        batch = {"kingfisher_nest": {
            "visual_plan": [
                {"tags": ["kingfisher_digging_bank"]},
                {"tags": ["kingfisher_entering_tunnel"]},
                {"tags": ["kingfisher_carrying_fish"]},
            ],
            "sources": [
                {"tags": ["kingfisher_digging_bank", "kingfisher_entering_tunnel"]},
                {"tags": ["kingfisher_entering_tunnel"]},
                {"tags": ["kingfisher_carrying_fish"]},
            ],
        }}
        self.assertTrue(validate_editorial_tags(batch))


if __name__ == "__main__":
    unittest.main()

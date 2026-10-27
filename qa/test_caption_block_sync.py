"""Caption synchronization regression tests without loading Kokoro or FFmpeg."""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_video.py"


def load_caption_clock():
    source = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = {"_normalize_plan_text", "weight", "caption_word_intervals"}
    selected = [node for node in source.body
                if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(selected) == len(names)
    scope = {"re": re}
    exec(compile(ast.Module(body=selected, type_ignores=[]),
                 str(SCRIPT), "exec"), scope)
    return scope["caption_word_intervals"]


clock = load_caption_clock()


class KokoroCaptionTiming(unittest.TestCase):
    def test_uses_actual_block_boundaries(self):
        text = "Why this bird? Watch it shake its feathers."
        timeline = [
            {"text": "Why this bird?", "start": 0.0, "end": 3.0},
            {"text": "Watch it shake its feathers.", "start": 3.0, "end": 9.0},
        ]
        words, starts, ends = clock(text, 9.0, timeline)
        self.assertEqual(words, text.split())
        self.assertEqual(len(starts), len(words))
        self.assertAlmostEqual(ends[2], 3.0, places=4)
        self.assertGreaterEqual(starts[3], 3.0)
        self.assertAlmostEqual(ends[-1], 9.0, places=4)
        self.assertTrue(all(a <= b for a, b in zip(starts, ends)))
        self.assertTrue(all(a <= b for a, b in zip(ends, starts[1:])))

    def test_rejects_mismatched_script(self):
        with self.assertRaisesRegex(RuntimeError, "do not match"):
            clock("Red panda climbs.", 3.0,
                  [{"text": "Sea otter swims.", "start": 0, "end": 3}])

    def test_rejects_non_monotonic_blocks(self):
        with self.assertRaisesRegex(RuntimeError, "boundaries"):
            clock("First block. Second block.", 4.0, [
                {"text": "First block.", "start": 0, "end": 3},
                {"text": "Second block.", "start": 2, "end": 4},
            ])

    def test_rejects_duration_mismatch(self):
        with self.assertRaisesRegex(RuntimeError, "duration"):
            clock("One sentence.", 5.0,
                  [{"text": "One sentence.", "start": 0, "end": 4}])

    def test_legacy_mode_retained(self):
        words, starts, ends = clock("One two three.", 4.0)
        self.assertEqual(len(words), 3)
        self.assertEqual(len(starts), 3)
        self.assertAlmostEqual(ends[-1], 4.0)


if __name__ == "__main__":
    unittest.main()

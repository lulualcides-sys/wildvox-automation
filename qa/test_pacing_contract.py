"""Regression tests for WildVox 6-8 second footage cadence.

Loads the production cadence guard by AST, avoiding heavy TTS imports.
"""
import ast
from pathlib import Path
import unittest

GENERATOR = Path(__file__).resolve().parents[1] / "scripts" / "generate_video.py"


def load_cadence_guard():
    tree = ast.parse(GENERATOR.read_text(encoding="utf-8"))
    matches = [node for node in tree.body
               if isinstance(node, ast.FunctionDef)
               and node.name == "validate_shot_cadence"]
    if len(matches) != 1:
        raise RuntimeError("Production shot cadence guard is missing")
    namespace = {}
    exec(compile(ast.Module(body=matches, type_ignores=[]),
                 str(GENERATOR), "exec"), namespace)
    return namespace["validate_shot_cadence"]


class ShotCadenceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.check = staticmethod(load_cadence_guard())

    def test_rejects_six_shots_in_34_seconds(self):
        with self.assertRaisesRegex(RuntimeError, "6-8"):
            self.check(34.0, 6)

    def test_accepts_six_shots_in_37_seconds(self):
        self.check(37.0, 6)

    def test_rejects_overlong_shots(self):
        with self.assertRaisesRegex(RuntimeError, "6-8"):
            self.check(44.0, 5)

    def test_photo_exception_not_subject_to_video_cadence(self):
        self.check(34.0, 8, allow_photo_only=True)


if __name__ == "__main__":
    unittest.main()

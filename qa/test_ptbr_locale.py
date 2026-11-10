"""Offline locale regression: do not silently fall back to English TTS."""
import ast
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "scripts" / "generate_video.py"
tree = ast.parse(GEN.read_text(encoding="utf-8"))
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name in ("_normalize_plan_text", "narration_preset", "weight")]
definitions = [node for node in tree.body if isinstance(node, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "NARRATION_VOICES"
                       for t in node.targets)]
assert len(functions) == 3 and len(definitions) == 1, "Missing production locale functions"
env = {"re": re}
exec(compile(ast.Module(body=definitions + functions, type_ignores=[]),
             str(GEN), "exec"), env)

sys.path.insert(0, str(ROOT / "scripts"))
from tiktok_credits import attributed_tiktok_caption


class WildVoxPortugueseLocaleTest(unittest.TestCase):
    def test_brazilian_voice(self):
        self.assertEqual(env["narration_preset"]("pt-BR"), ("p", "pm_alex"))
        self.assertEqual(env["narration_preset"]("pt-BR", "pm_alex"),
                         ("p", "pm_alex"))
        self.assertEqual(env["narration_preset"](), ("a", "am_michael"))

    def test_no_english_voice_for_portuguese(self):
        for invalid in ("am_michael", "pf_dora", "pm_santa"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    env["narration_preset"]("pt-BR", invalid)

    def test_no_unsupported_locale(self):
        with self.assertRaises(ValueError):
            env["narration_preset"]("pt-PT")

    def test_accents_preserved_across_exact_narration_blocks(self):
        norm = env["_normalize_plan_text"]
        full = "O gato não caça agora. Ele observa a água!"
        blocks = ["O gato não caça agora.", "Ele observa a água!"]
        self.assertEqual(norm(" ".join(blocks)), norm(full))
        self.assertNotEqual(norm("não"), norm("nao"))
        self.assertNotEqual(norm("ação"), norm("a o"))
        self.assertGreater(env["weight"]("coração"), 1)

    def test_ptbr_role_callouts_are_not_english(self):
        from cinematic_fx import build_events
        events = build_events([
            {"start": 0, "end": 2.5, "story_role": "hook", "language": "pt-BR"},
            {"start": 2.5, "end": 5.0, "story_role": "payoff", "language": "pt-BR"}
        ])
        self.assertTrue(any("OLHE BEM" in e for e in events))
        self.assertTrue(any("A REVELAÇÃO" in e for e in events))
        self.assertFalse(any("THE REVEAL" in e for e in events))

    def test_ptbr_caption_keeps_all_legal_credits(self):
        daily = json.loads((ROOT / "configs/daily.json").read_text(encoding="utf-8"))
        entry = dict(next(iter(daily.values())))
        entry["language"] = "pt-BR"
        entry["caption"] = "Um pequeno comportamento felino. #WildVox #Gatos"
        result = attributed_tiktok_caption(entry)
        self.assertIn("Créditos dos vídeos", result)
        self.assertIn(entry["sources"][0]["sourcePage"], result)
        self.assertLessEqual(len(result), 2200)


if __name__ == "__main__":
    unittest.main()

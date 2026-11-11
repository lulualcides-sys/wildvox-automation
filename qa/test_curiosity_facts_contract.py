"""Regression tests for fact-led WildVox scripts (not shot-by-shot descriptions)."""
import copy
import json
import unittest
from pathlib import Path
from validate_curiosity_facts import validate_batch, validate_entry

ROOT = Path(__file__).resolve().parents[1]


def sample():
    return {
        "revision": "2026-11-11-gatos-comunicacao-v1",
        "publication_hold": True, "language": "pt-BR", "voice": "pm_alex",
        "script": "Por que os gatos ronronam? Nem todo ronronar indica prazer. Existem diferentes contextos e mecanismos investigados.",
        "visual_plan": [
            {"text": "Por que os gatos ronronam?", "scene": "Gato em repouso", "tags": ["cat_rest"], "story_role": "hook"},
            {"text": "Nem todo ronronar", "scene": "Gato em interação", "tags": ["cat_social"], "story_role": "setup"},
            {"text": "indica prazer.", "scene": "Gato em movimento", "tags": ["cat_move"], "story_role": "action"},
            {"text": "Existem diferentes contextos", "scene": "Gato em descanso", "tags": ["cat_sleep"], "story_role": "explanation"},
            {"text": "e mecanismos investigados.", "scene": "Gato próximo a outro", "tags": ["cat_pair"], "story_role": "payoff"},
        ],
        "curiosity_fact_sheet": {
            "hook_question": "Por que os gatos podem ronronar em situações diferentes?",
            "verified_fact": "O ronronar ocorre em múltiplos contextos, não apenas no descanso.",
            "biological_explanation": "A vocalização depende de mecanismos fisiológicos e comunicação felina.",
            "comparison_or_consequence": "Diferentes vocalizações podem expressar necessidades diferentes.",
            "visual_evidence_strategy": "Mostrar gatos reais em repouso e interação, sem dizer que o som é captado no vídeo.",
            "fact_sources": [{
                "claim": "Gatos podem ronronar em diferentes contextos.",
                "url": "https://www.example.edu/research/purring",
                "publisher": "Instituição acadêmica demonstrativa",
                "reference_title": "Literatura sobre vocalizações de felinos",
            }, {
                "claim": "A vocalização felina possui mecanismos biológicos estudados.",
                "url": "https://www.example.org/research/feline-vocalization",
                "publisher": "Instituição científica demonstrativa independente",
                "reference_title": "Estudos sobre mecanismos de vocalização felina",
            }],
        },
    }


class CuriosityEditorialContract(unittest.TestCase):
    def test_current_batch_passes_only_if_revisions_predate_new_gate(self):
        batch = json.loads((ROOT / "configs/daily.json").read_text(encoding="utf-8"))
        validate_batch(batch)

    def test_complete_fact_sheet_passes_structural_gate(self):
        validate_entry("cat", sample())

    def test_future_descriptive_only_candidate_is_blocked(self):
        item = sample()
        item.pop("curiosity_fact_sheet")
        with self.assertRaisesRegex(ValueError, "curiosity_fact_sheet"):
            validate_entry("cat", item)

    def test_media_clip_not_allowed_as_fact_reference(self):
        item = sample()
        item["curiosity_fact_sheet"]["fact_sources"][0]["url"] = "https://commons.wikimedia.org/wiki/File:Cat.webm"
        with self.assertRaisesRegex(ValueError, "not an independent scientific citation"):
            validate_entry("cat", item)

    def test_one_fact_source_is_rejected(self):
        item = sample()
        item["curiosity_fact_sheet"]["fact_sources"].pop()
        with self.assertRaisesRegex(ValueError, "independent fact_sources"):
            validate_entry("cat", item)

    def test_duplicate_fact_source_is_rejected(self):
        item = sample()
        item["curiosity_fact_sheet"]["fact_sources"][1]["url"] = item["curiosity_fact_sheet"]["fact_sources"][0]["url"]
        with self.assertRaisesRegex(ValueError, "duplicate scientific URLs"):
            validate_entry("cat", item)

    def test_same_publisher_is_rejected(self):
        item = sample()
        item["curiosity_fact_sheet"]["fact_sources"][1]["publisher"] = item["curiosity_fact_sheet"]["fact_sources"][0]["publisher"]
        with self.assertRaisesRegex(ValueError, "two independent scientific publishers"):
            validate_entry("cat", item)

    def test_release_hold_cannot_be_removed(self):
        item = sample()
        item["publication_hold"] = False
        with self.assertRaisesRegex(ValueError, "publication_hold"):
            validate_entry("cat", item)

    def test_fact_and_explanation_must_be_distinct(self):
        item = sample()
        item["curiosity_fact_sheet"]["biological_explanation"] = item["curiosity_fact_sheet"]["verified_fact"]
        with self.assertRaisesRegex(ValueError, "must be distinct"):
            validate_entry("cat", item)


if __name__ == "__main__":
    unittest.main()

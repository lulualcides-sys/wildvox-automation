"""Research-only live config preflight for Nov 2; never renders or publishes."""
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from semantic_shots import validate_editorial_tags
from test_narrative_contract import validate_narrative_arc

class NovemberTwoPreflight(unittest.TestCase):
    def test_all_current_source_tags_match_distinct_spoken_blocks(self):
        data=json.loads((ROOT/"configs/daily.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data),5)
        self.assertTrue(validate_editorial_tags(data))
        for key,entry in data.items():
            with self.subTest(key=key):
                self.assertTrue(entry["revision"].startswith("2026-11-02-"))
                self.assertTrue(entry["publication_hold"])
                self.assertEqual((entry["min_duration"],entry["max_duration"]),(30,45))
                self.assertEqual(len(entry["visual_plan"]),6)
                self.assertEqual(len(entry["sources"]),8)
                self.assertTrue(all(s["type"]=="video" for s in entry["sources"]))
                self.assertEqual(entry["script"]," ".join(b["text"] for b in entry["visual_plan"]))
                validate_narrative_arc(entry)

if __name__=="__main__":
    unittest.main()

"""CI sem GPU e sem Kokoro: executa as regras reais do gerador via AST.

Ao contrario de testes de texto simulados, usa validate_daily_batch
do codigo de producao. Nunca gera, publica ou agenda video.
"""
import ast
import copy
import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit,urlunsplit

ROOT=Path(__file__).resolve().parents[1]
GENERATOR=ROOT/"scripts"/"generate_video.py"
DAILY=ROOT/"configs"/"daily.json"

def load_validation():
    tree=ast.parse(GENERATOR.read_text(encoding="utf-8"))
    functions=[n for n in tree.body if isinstance(n,ast.FunctionDef)
               and n.name in ("canonical_url","validate_daily_batch")]
    if len(functions)!=2:raise RuntimeError("Regras reais do WildVox não encontradas")
    out={"urlsplit":urlsplit,"urlunsplit":urlunsplit}
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(GENERATOR),"exec"),out)
    return out["validate_daily_batch"]

class EditorialContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.check=staticmethod(load_validation())
        cls.daily=json.loads(DAILY.read_text(encoding="utf-8"))

    def test_current_daily_five_passes_current_generator_gate(self):
        self.assertEqual(len(self.daily),5)
        self.check(copy.deepcopy(self.daily))

    def test_rejects_duplicate_url_across_videos(self):
        batch=copy.deepcopy(self.daily)
        keys=list(batch)
        # Mesmo URL, ainda que acrescente querystring, tem que bloquear.
        url=batch[keys[0]]["sources"][0]
        url=url if isinstance(url,str) else url["url"]
        batch[keys[1]]["sources"][0]={"url":url+"?tracking=other","type":"video"}
        with self.assertRaisesRegex(RuntimeError,"Duplicate media URL"):
            self.check(batch)

    def test_rejects_wrong_video_count(self):
        batch=copy.deepcopy(self.daily)
        batch.pop(next(iter(batch)))
        with self.assertRaisesRegex(RuntimeError,"exactly 5"):
            self.check(batch)

    def test_no_placeholder_or_missing_configs(self):
        for key,value in self.daily.items():
            self.assertTrue(str(value.get("title") or "").strip(),key)
            self.assertTrue(str(value.get("script") or "").strip(),key)

if __name__=="__main__":unittest.main()

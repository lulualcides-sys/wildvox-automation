#!/usr/bin/env python3
"""Research-branch ONLY preflight: no daily.json write and no rendering."""
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"qa"))
sys.path.insert(0,str(ROOT/"scripts"))
from test_editorial_contract import load_validation
from test_narrative_contract import validate_narrative_arc
from semantic_shots import validate_editorial_tags
from audit_commons_sources import validate_source_mix

CANDIDATE=ROOT/"qa"/"daily-prep-candidate-2026-10-31.json"

def main():
    batch=json.loads(CANDIDATE.read_text(encoding="utf-8"))
    assert len(batch)==5
    assert all(v["revision"].startswith("2026-10-31") for v in batch.values())
    assert all(v["publication_hold"] is True for v in batch.values())
    assert all((v["min_duration"],v["max_duration"])==(30,45) for v in batch.values())
    validate_editorial_tags(batch)
    load_validation()(batch)
    validate_source_mix(batch)
    for v in batch.values():
        validate_narrative_arc(v)
    print("RESEARCH CANDIDATE: schema, exact-script, semantic tags, narrative arc, 40 unique URLs, 30-45s all PASS; NOT visual approval",flush=True)
    for name in ["test_narrative_contract.py","test_cinematic_fx.py",
                 "test_semantic_shots.py","test_commons_source_mix.py"]:
        subprocess.run([sys.executable,"-m","unittest","discover",
                        "-s",str(ROOT/"qa"),"-p",name,"-v"],check=True)
    print("RESEARCH CANDIDATE: targeted tests PASS",flush=True)
    subprocess.run([sys.executable,str(ROOT/"scripts"/"audit_commons_sources.py"),
                    "--config",str(CANDIDATE)],check=True)
    print("RESEARCH CANDIDATE: live Commons license check PASS; visual proof and creator attribution still pending",flush=True)

if __name__=="__main__":main()

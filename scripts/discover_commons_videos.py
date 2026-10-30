#!/usr/bin/env python3
"""Research-only candidate preflight; does not change production or publish."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "qa"))
sys.path.insert(0, str(ROOT / "scripts"))
from test_editorial_contract import load_validation
from test_narrative_contract import validate_narrative_arc
from cinematic_fx import build_events

path = ROOT / "qa" / "daily-prep-candidate-2026-10-30.json"
batch = json.loads(path.read_text(encoding="utf-8"))
load_validation()(batch)
assert len(batch) == 5
for key, cfg in batch.items():
    assert cfg["min_duration"] == 30 and cfg["max_duration"] == 45
    assert cfg["publication_hold"] is True
    assert cfg["revision"].startswith("2026-10-30-")
    validate_narrative_arc(cfg)
    assert len(cfg["sources"]) == 8
    assert len({x["url"] for x in cfg["sources"]}) == 8
    assert all(x["type"] == "video" for x in cfg["sources"])
    # No unverified coordinate pointers; animated role labels still tested.
    timeline = [{"start":i * 6.0, "end":(i+1)*6.0,
                 "story_role":x["story_role"],
                 "overlay_label":x.get("overlay_label"),
                 "fx":x.get("fx",[])} for i,x in enumerate(cfg["visual_plan"])]
    build_events(timeline)
    print("EDITORIAL_PASS",key,"words",len(cfg["script"].split()),"assets",len(cfg["sources"]),flush=True)
print("SCHEMA_AND_NARRATIVE_PASS",flush=True)
subprocess.run([sys.executable,"-m","unittest","qa.test_cinematic_fx",
                "qa.test_narrative_contract","qa.test_editorial_contract"],
               check=True,cwd=ROOT)
print("TARGETED_TESTS_PASS",flush=True)
subprocess.run([sys.executable,"scripts/audit_commons_sources.py","--config",
                str(path.relative_to(ROOT))],check=True,cwd=ROOT)
print("COMMONS_RIGHTS_AUDIT_PASS",flush=True)

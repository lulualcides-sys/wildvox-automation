#!/usr/bin/env python3
"""Research-only preflight of 31 Oct five-species footage-first batch.

Structural approval never substitutes for frame-by-frame editorial clearance.
Do not write configs/daily.json or trigger rendering from this file.
"""
import copy, json, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"qa"),str(ROOT/"scripts")]
from test_editorial_contract import load_validation
from test_narrative_contract import validate_narrative_arc
from semantic_shots import validate_editorial_tags
from audit_commons_sources import validate_source_mix
from tiktok_credits import attributed_tiktok_caption

candidate=ROOT/"qa"/"daily-prep-candidate-2026-10-31-footage-first.json"
batch=json.loads(candidate.read_text(encoding="utf-8"))
assert len(batch)==5, "Must contain exactly five stories"
assert validate_source_mix(batch)==40, "Need 40 genuine video sources"
assert validate_editorial_tags(batch)
load_validation()(copy.deepcopy(batch))
urls=set()
for key,entry in batch.items():
    assert entry["revision"].startswith("2026-10-31-"),key
    assert entry["min_duration"]==30 and entry["max_duration"]==45,key
    assert entry["publication_hold"] is True,key
    assert len(entry["visual_plan"])==6,key
    validate_narrative_arc(entry)
    assert re.sub(r"\s+"," ",entry["script"]).strip()==re.sub(
        r"\s+"," "," ".join(b["text"] for b in entry["visual_plan"])).strip(),key
    for source in entry["sources"]:
        assert source["url"] not in urls,source["url"]
        urls.add(source["url"])
        assert source["type"]=="video"
        assert source["sourcePage"].startswith("https://commons.wikimedia.org/wiki/File:")
        assert source["author"] and source["license"] and source["license_url"]
        assert "by-sa" not in source["license"].lower()
    caption=attributed_tiktok_caption(entry)
    assert len(caption)<=2200,key
    print("STRUCTURAL_PASS",key,len(entry["script"].split()),"words",len(caption),"caption chars")
assert len(urls)==40
print("RESEARCH_ONLY: 5 structural candidates, 40 distinct licensed-source records.")
print("NOT APPROVED: actual shot windows, motion, 8 usable source scenes per story and final MP4 require independent review.")

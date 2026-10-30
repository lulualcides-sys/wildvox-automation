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

# Verify original file checksums, not only unique filenames/URLs. Artist metadata
# is independently read from Commons for each title; unresolved credit formats
# remain a human QA blocker, not a fabricated identity.
import html
import re
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from time import sleep
seen_sha = {}
for index in range(0, 40, 10):
    pairs = [(key, item) for key, cfg in batch.items()
             for item in cfg["sources"]][index:index + 10]
    titles = ["File:" + item["assetTitle"] for key, item in pairs]
    params = urlencode({"action":"query","format":"json","formatversion":2,
                        "prop":"imageinfo","iiprop":"sha1|extmetadata|size",
                        "titles":"|".join(titles)})
    req = Request("https://commons.wikimedia.org/w/api.php?" + params,
                  headers={"User-Agent":"WildVoxEditorialAudit/1.0 (public GitHub project)"})
    with urlopen(req,timeout=35) as response:
        payload = json.load(response)
    pages = {p["title"].casefold():p for p in payload.get("query",{}).get("pages",[])}
    for key, source in pairs:
        title = ("File:" + source["assetTitle"]).casefold()
        page = pages.get(title)
        assert page and page.get("imageinfo"),"Missing original file: "+title
        info = page["imageinfo"][0]
        sha1 = info.get("sha1")
        assert sha1 and sha1 not in seen_sha, "Identical media bytes: "+title+" and "+str(seen_sha.get(sha1))
        seen_sha[sha1] = title
        artist_html = (info.get("extmetadata",{}).get("Artist",{}) or {}).get("value","")
        artist = html.unescape(re.sub(r"<[^>]*>"," ",artist_html)).strip()
        if not artist:
            print("CREATOR_REVIEW",source["assetTitle"],"original Commons artist field blank",flush=True)
        else:
            expected = str(source["author"])
            print("CREATOR",source["assetTitle"],"claimed",expected[:65],
                  "Commons",artist[:95],flush=True)
    sleep(.2)
assert len(seen_sha) == 40
print("UNIQUE_BYTES_AND_CREATOR_RECORDS_CHECKED",len(seen_sha),flush=True)


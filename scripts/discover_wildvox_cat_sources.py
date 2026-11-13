#!/usr/bin/env python3
"""WildVox Commons source discovery: CC0/PD/CC BY candidates ONLY, never publication."""
import html
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

API = "https://commons.wikimedia.org/w/api.php"
UA = "WildVoxSourceDiscovery/1.0 (github.com/lulualcides-sys/wildvox-automation; editorial research)"
CATEGORIES = [
    "Category:Videos of cats",
    "Category:Videos of eating cats",
    "Category:Videos of drinking cats",
    "Category:Videos of grooming cats",
    "Category:Videos of playing cats",
    "Category:Videos of kittens",
    "Category:Outdoor cats",
]
ACCEPTED = {"cc0", "cc by 2.0", "cc by 2.5", "cc by 3.0", "cc by 4.0", "public domain", "pd-self"}
def request(params):
    args = {"action": "query", "format": "json", "formatversion": 2, **params}
    req = Request(API + "?" + urlencode(args), headers={"User-Agent": UA, "Accept": "application/json"})
    with urlopen(req, timeout=45) as response:
        return json.load(response)

def clean(value):
    return html.unescape(re.sub("<[^>]+>", "", str(value or ""))).strip()

def license_kind(data):
    meta = data.get("extmetadata") or {}
    value = clean((meta.get("LicenseShortName") or {}).get("value")).lower().replace("-", " ")
    # Explicitly exclude SA, NC, ND, unknown, and misleading CC0 text in Commons metadata.
    if "share" in value or " sa" in value or "nc" in value or "nd" in value:
        return None
    if value not in ACCEPTED:
        return None
    url = clean((meta.get("LicenseUrl") or {}).get("value"))
    if value.startswith("cc by") and "/licenses/by/" not in url.lower():
        return None
    return value, url

def main():
    old = json.loads(Path("configs/daily.json").read_text(encoding="utf-8"))
    used = {str(s.get("assetTitle", "")).lower() for c in old.values() for s in c.get("sources", []) if isinstance(s,dict)}
    seen = set()
    results = []
    failures = []
    for cat in CATEGORIES:
        cursor = {}
        for page_no in range(3):
            try:
                result = request({
                    "generator": "categorymembers", "gcmtitle": cat,
                    "gcmtype": "file", "gcmlimit": 100,
                    "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
                    **cursor
                })
            except Exception as exc:
                failures.append({"category":cat,"error":str(exc)[:180]})
                break
            for page in result.get("query",{}).get("pages",[]):
                title = page.get("title", "")
                filename = title.removeprefix("File:")
                if title in seen or not re.search(r"\.(webm|ogv|ogg|mp4)$", title, re.I):
                    continue
                seen.add(title)
                if filename.lower() in used:
                    continue
                info = (page.get("imageinfo") or [{}])[0]
                if not info.get("mime", "").startswith("video/"):
                    continue
                lic = license_kind(info)
                if not lic:
                    continue
                meta = info.get("extmetadata") or {}
                author = clean((meta.get("Artist") or {}).get("value"))
                if not author or not info.get("url"):
                    continue
                results.append({
                    "assetTitle": filename,
                    "sourcePage": "https://commons.wikimedia.org/wiki/File:" + quote(filename.replace(" ","_"), safe="()'"),
                    "sourceUrl": info["url"],
                    "license": lic[0],
                    "license_url": lic[1],
                    "author": author[:220],
                    "description": clean((meta.get("ImageDescription") or {}).get("value"))[:230],
                    "size_bytes": info.get("size"),
                    "categories": [cat],
                    "status": "CANDIDATE_UNREVIEWED",
                    "publication_hold": True,
                })
            cursor = result.get("continue") or {}
            if not cursor:
                break
            time.sleep(0.2)
    results.sort(key=lambda x:(x.get("size_bytes") or 999999999, x["assetTitle"].lower()))
    output = {
        "editorial_day": "2026-11-12",
        "candidate_topic": "Por que gatos nao sentem o sabor doce como humanos?",
        "source_count": len(results), "sources": results,
        "failures": failures,
        "editorial_status": "RESEARCH_ONLY_NOT_INSPECTED",
        "publication_hold": True,
        "fact_sources": [
            {"url":"https://journals.plos.org/plosgenetics/article?id=10.1371/journal.pgen.0010003","publisher":"PLOS Genetics","reference_title":"Pseudogenization of a Sweet-Receptor Gene Accounts for Cats' Indifference toward Sugar"},
            {"url":"https://pubmed.ncbi.nlm.nih.gov/22411809/","publisher":"PNAS / PubMed","reference_title":"Major taste loss in carnivorous mammals"}
        ]
    }
    Path("source-pool-2026-11-12.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"eligible":len(results),"sample":[x["assetTitle"] for x in results[:20]],"failures":failures},ensure_ascii=False))
    if not results:
        sys.exit(2)
if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Research-only Commons original-footage index, 31 Oct 2026.

Does not touch daily.json or render. This discovery cannot establish actual
behavioral semantics: preview frames and full clips must be inspected later.
"""
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://commons.wikimedia.org/w/api.php"
UA = "WildVoxSourceResearch/1.0 (public GitHub project; footage research)"
SPECIES = {
    "capybara": ["Hydrochoerus hydrochaeris", "capybara"],
    "common_raven": ["Corvus corax", "common raven"],
    "japanese_macaque": ["Macaca fuscata", "Japanese macaque"],
    "great_blue_heron": ["Ardea herodias", "great blue heron"],
    "bottlenose_dolphin": ["Tursiops truncatus", "bottlenose dolphin"],
    "common_octopus": ["Octopus vulgaris", "common octopus"],
    "tokay_gecko": ["Gekko gecko", "tokay gecko"],
    "common_frog": ["Rana temporaria", "common frog"],
    "little_penguin": ["Eudyptula minor", "little penguin"],
}
def query(**params):
    q={"action":"query","format":"json","formatversion":2,**params}
    req=Request(API+"?"+urlencode(q),headers={"User-Agent":UA,"Accept":"application/json"})
    for i in range(3):
        try:
            with urlopen(req,timeout=30) as f:
                data=json.load(f)
            if data.get("error"):raise RuntimeError(data["error"])
            return data
        except Exception:
            if i==2:raise
            time.sleep(1+i*2)

def clean(text):
    return html.unescape(re.sub(r"<[^>]+>"," ",text or "")).replace("\n"," ").strip()[:180]

def main():
    all_found={}
    for key,phrases in SPECIES.items():
        names=set()
        for phrase in phrases:
            result=query(list="search",srsearch=phrase,srnamespace=6,srlimit=90)
            names.update(x["title"] for x in result.get("query",{}).get("search",[])
                         if re.search(r"\.(?:webm|ogv|ogg)$",x.get("title",""),re.I))
            time.sleep(.15)
        all_found[key]=names
        print(f"SEARCH {key} titles={len(names)}",flush=True)
    universe=sorted(set().union(*all_found.values()))
    data={}
    for i in range(0,len(universe),18):
        result=query(titles="|".join(universe[i:i+18]),prop="imageinfo",
                     iiprop="size|mime|extmetadata|sha1|url")
        for p in result.get("query",{}).get("pages",[]):
            if p.get("imageinfo"):
                info=p["imageinfo"][0]
                meta=info.get("extmetadata") or {}
                license=(meta.get("LicenseShortName") or {}).get("value") or ""
                if ("by-sa" in license.lower() or "by-nc" in license.lower()
                    or not license.lower().startswith(("cc by ","cc0","public domain","pd-","pd "))):
                    continue
                if not (info.get("mime","").startswith("video/") or info.get("mime")=="application/ogg"):
                    continue
                if int(info.get("size") or 0)<100000:continue
                data[p["title"]]={
                    "title":p["title"],"license":license,
                    "author":clean((meta.get("Artist") or {}).get("value")),
                    "description":clean((meta.get("ImageDescription") or {}).get("value")),
                    "size":info.get("size"),"sha1":info.get("sha1"),
                    "url":info.get("url"),
                    "sourcePage":info.get("descriptionurl"),
                    "license_url":(meta.get("LicenseUrl") or {}).get("value")
                }
        time.sleep(.12)
    summary={}
    for key,names in all_found.items():
        rows=sorted((data[n] for n in names if n in data),
                    key=lambda r:(-int(r["size"]),r["title"]))
        summary[key]={"searched_titles":len(names),"eligible":len(rows),
                      "candidates":rows}
        print("RESULT "+json.dumps({
            "species":key,"eligible":len(rows),
            "top":[{k:x[k] for k in ("title","license","author","description","size")}
                   for x in rows[:20]]
        },ensure_ascii=False),flush=True)
    Path("commons-discovery.json").write_text(
        json.dumps({"date":"2026-10-31","species":summary,"not_visual_approval":True},
                   indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
if __name__=="__main__":
    main()

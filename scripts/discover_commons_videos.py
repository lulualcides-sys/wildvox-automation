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
from urllib.error import HTTPError

API = "https://commons.wikimedia.org/w/api.php"
UA = "WildVoxSourceResearch/1.0 (public GitHub project; footage research)"
SPECIES = {
    "grey_heron": "Category:Videos of Ardea cinerea",
    "great_egret": "Category:Videos of Ardea alba",
    "common_raven": "Category:Videos of Corvus corax",
    "giraffe": "Category:Videos of Giraffa camelopardalis",
    "lion": "Category:Videos of Panthera leo",
    "grey_wolf": "Category:Videos of Canis lupus",
    "capybara": "Category:Videos of Hydrochoerus hydrochaeris",
    "octopus": "Category:Videos of Octopus vulgaris",
}
def query(**params):
    q={"action":"query","format":"json","formatversion":2,**params}
    req=Request(API+"?"+urlencode(q),headers={"User-Agent":UA,"Accept":"application/json"})
    for i in range(4):
        try:
            with urlopen(req,timeout=30) as f:
                data=json.load(f)
            if data.get("error"):raise RuntimeError(data["error"])
            return data
        except HTTPError as exc:
            if exc.code != 429 or i == 3: raise
            wait = min(35, max(7, int(exc.headers.get("Retry-After") or 7)) + 5*i)
            print(f"COMMONS RATE LIMIT: waiting {wait}s", flush=True)
            time.sleep(wait)
        except Exception:
            if i==3:raise
            time.sleep(2+i*3)

def clean(text):
    return html.unescape(re.sub(r"<[^>]+>"," ",text or "")).replace("\n"," ").strip()[:180]

def main():
    summary={}
    for key, category in SPECIES.items():
        result=query(generator="categorymembers",gcmtitle=category,
                     gcmtype="file",gcmlimit=100,prop="imageinfo",
                     iiprop="size|mime|extmetadata|sha1|url")
        rows=[]
        for page in result.get("query",{}).get("pages",[]):
            title=page.get("title","")
            if not re.search(r"\.(?:webm|ogv|ogg)$",title,re.I):continue
            info=(page.get("imageinfo") or [{}])[0]
            meta=info.get("extmetadata") or {}
            license=(meta.get("LicenseShortName") or {}).get("value") or ""
            if ("by-sa" in license.lower() or "by-nc" in license.lower()
                or not license.lower().startswith(("cc by ","cc0","public domain","pd-","pd "))):
                continue
            if not (info.get("mime","").startswith("video/") or info.get("mime")=="application/ogg"):continue
            if int(info.get("size") or 0)<100000:continue
            rows.append({
                "title":title,"license":license,
                "author":clean((meta.get("Artist") or {}).get("value")),
                "description":clean((meta.get("ImageDescription") or {}).get("value")),
                "size":info.get("size"),"sha1":info.get("sha1"),
                "url":info.get("url"),"sourcePage":info.get("descriptionurl"),
                "license_url":(meta.get("LicenseUrl") or {}).get("value")
            })
        rows.sort(key=lambda x:(-int(x["size"]),x["title"]))
        summary[key]={"category":category,"eligible":len(rows),"candidates":rows}
        print("RESULT "+json.dumps({"species":key,"eligible":len(rows),
              "top":[{k:x[k] for k in ("title","license","author","description","size")}
              for x in rows[:25]]},ensure_ascii=False),flush=True)
        time.sleep(2)
    Path("commons-discovery.json").write_text(
        json.dumps({"date":"2026-10-31","species":summary,"not_visual_approval":True},
                   indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
if __name__=="__main__":
    main()

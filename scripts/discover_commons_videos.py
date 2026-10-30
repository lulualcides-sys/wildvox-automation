#!/usr/bin/env python3
"""WildVox 2026-10-30 research-only Commons video inventory; no publishing."""
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

API = "https://commons.wikimedia.org/w/api.php"
UA = "WildVoxSourceResearch/1.0 (source verification; GitHub project)"
SUBJECTS = {
    "kingfisher": ["Alcedo atthis", "kingfisher"],
    "mantis_religiosa": ["Mantis religiosa", "praying mantis"],
    "bald_eagle": ["Haliaeetus leucocephalus", "bald eagle"],
    "great_blue_heron": ["Ardea herodias", "great blue heron"],
    "humpback_whale": ["Megaptera novaeangliae", "humpback whale"],
    "american_alligator": ["Alligator mississippiensis", "American alligator"],
    "american_beaver": ["Castor canadensis", "American beaver"],
    "california_sea_lion": ["Zalophus californianus", "California sea lion"],
    "common_octopus": ["Octopus vulgaris", "common octopus"]
}
CATEGORIES = {
    "kingfisher": ["Videos of Alcedo atthis", "Alcedo atthis videos"],
    "mantis_religiosa": ["Mantis religiosa videos"],
    "bald_eagle": ["Videos of Haliaeetus leucocephalus", "Haliaeetus leucocephalus videos"],
    "great_blue_heron": ["Videos of Ardea herodias", "Ardea herodias videos"],
    "humpback_whale": ["Videos of Megaptera novaeangliae", "Megaptera novaeangliae videos"],
    "american_alligator": ["Videos of Alligator mississippiensis", "Alligator mississippiensis videos"],
    "american_beaver": ["Videos of Castor canadensis", "Castor canadensis videos"],
    "california_sea_lion": ["Videos of Zalophus californianus", "Zalophus californianus videos"],
    "common_octopus": ["Videos of Octopus vulgaris", "Octopus vulgaris videos"]
}
VIDEO = re.compile(r"\.(?:webm|ogv|ogg|mp4)$", re.I)
def query(params):
    data = {"action": "query", "format": "json", "formatversion": 2, **params}
    req = Request(API + "?" + urlencode(data), headers={"User-Agent": UA, "Accept": "application/json"})
    for i in range(3):
        try:
            with urlopen(req, timeout=40) as resp:
                result = json.load(resp)
            if result.get("error"):
                raise RuntimeError(str(result["error"]))
            return result
        except Exception:
            if i == 2: raise
            time.sleep(2 * (i + 1))
def clean(s):
    return html.unescape(re.sub(r"<[^>]*>", "", str(s or ""))).strip()[:150]
def license_ok(s):
    s = s.lower().strip().replace("_", " ")
    return (s.startswith("cc by ") and "sa" not in s and "nc" not in s) or s.startswith(("cc0", "public domain", "pd-", "pd "))
def main():
    result = {}
    for subject, phrases in SUBJECTS.items():
        titles = set()
        for phrase in phrases[:2]:
            for q in ('filetype:video ' + phrase,):
                try:
                    response = query({"list": "search", "srsearch": q, "srnamespace": 6, "srlimit": 100})
                    titles.update(row["title"] for row in response.get("query", {}).get("search", [])
                                  if VIDEO.search(row.get("title", "")))
                except Exception as e:
                    print("SEARCH_WARNING", subject, phrase, str(e)[:120])
                time.sleep(.08)
        for category in CATEGORIES.get(subject, []):
            try:
                response = query({"generator":"categorymembers","gcmtitle":"Category:"+category,
                                  "gcmtype":"file","gcmlimit":150,"prop":"imageinfo","iiprop":"size"})
                titles.update(p["title"] for p in response.get("query",{}).get("pages",[])
                              if VIDEO.search(p.get("title","")))
            except Exception as e:
                print("CATEGORY_WARNING",subject,category,str(e)[:80])
        rows = []
        names = sorted(titles)
        for offset in range(0, len(names), 35):
            try:
                response = query({"prop": "imageinfo|categories", "titles": "|".join(names[offset:offset+35]),
                                  "iiprop": "url|size|mime|extmetadata", "cllimit": "max"})
            except Exception as e:
                print("INFO_WARNING", subject, str(e)[:120])
                continue
            for page in response.get("query", {}).get("pages", []):
                info = (page.get("imageinfo") or [{}])[0]
                md = info.get("extmetadata") or {}
                lic = clean((md.get("LicenseShortName") or {}).get("value"))
                mime = info.get("mime", "")
                size = int(info.get("size") or 0)
                if not license_ok(lic) or not mime.startswith(("video/", "application/ogg")) or size < 100000:
                    continue
                title = page["title"].removeprefix("File:")
                categories = [x.get("title","").removeprefix("Category:") for x in page.get("categories", [])]
                rows.append({
                    "title": title, "license": lic,
                    "license_url": clean((md.get("LicenseUrl") or {}).get("value")),
                    "author": clean((md.get("Artist") or {}).get("value")) or clean((md.get("Attribution") or {}).get("value")),
                    "description": clean((md.get("ImageDescription") or {}).get("value"))[:130],
                    "size": size, "mime": mime,
                    "sourcePage": "https://commons.wikimedia.org/wiki/File:" + quote(title.replace(" ","_"), safe="()"),
                    "url": "https://commons.wikimedia.org/wiki/Special:FilePath/" + quote(title, safe="()"),
                    "categories": categories[:10]
                })
            time.sleep(.1)
        rows.sort(key=lambda x: (-int(bool(re.search(phrases[0], x["title"], re.I))),
                                 -int(bool(re.search(phrases[1], x["title"], re.I))),
                                 -min(x["size"], 50000000)))
        result[subject] = {"found": len(titles), "free_videos": len(rows), "candidates": rows[:30]}
        print("SUBJECT", subject, "search", len(titles), "free", len(rows))
        for item in rows[:22]:
            print("CANDIDATE", json.dumps({"subject":subject,"title":item["title"],
                   "license":item["license"],"author":item["author"],"size":item["size"],
                   "description":item["description"][:70],"categories":item["categories"][:4]},
                   ensure_ascii=False))
    Path("commons-discovery.json").write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
if __name__ == "__main__":
    main()

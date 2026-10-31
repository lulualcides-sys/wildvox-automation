#!/usr/bin/env python3
"""31 Oct footage-first exploratory Commons search; research only, no publishing."""
import json, re, time, html
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API="https://commons.wikimedia.org/w/api.php"
UA="WildVoxFootageFirst/1.0 (source research; GitHub public repository)"
TOPICS={
  "mallard_duck": ["Anas platyrhynchos","Category:Videos of Anas platyrhynchos"],
  "eurasian_red_squirrel": ["Sciurus vulgaris","Category:Videos of Sciurus vulgaris"],
  "european_robin": ["Erithacus rubecula","Category:Videos of Erithacus rubecula"],
  "domestic_goat": ["goats","Category:Videos of goats"],
  "rock_pigeon": ["Columba livia domestica","Category:Videos of Columba livia"]
}

def api(params):
    url=API+"?"+urlencode({"action":"query","format":"json","formatversion":"2",**params})
    for attempt in range(2):
        try:
            with urlopen(Request(url,headers={"User-Agent":UA,"Accept":"application/json"}),timeout=15) as h:
                result=json.load(h)
            if result.get("error"): raise RuntimeError(str(result["error"])[:200])
            return result
        except (HTTPError,URLError,TimeoutError,RuntimeError) as e:
            if attempt==1: raise
            time.sleep(1.5)
def file_name(t):
    return t.startswith("File:") and re.search(r"\.(webm|ogv|ogg|mp4)$",t,re.I)
def main():
    result={}
    for topic,terms in TOPICS.items():
        titles=set()
        for phrase in terms:
            try:
                if phrase.startswith("Category:"):
                    p=api({"generator":"categorymembers","gcmtitle":phrase,"gcmtype":"file","gcmlimit":"150","prop":"info"})
                    titles.update(x.get("title","") for x in p.get("query",{}).get("pages",[]) if file_name(x.get("title","")))
                else:
                    p=api({"list":"search","srsearch":phrase+" filetype:video","srnamespace":"6","srlimit":"70"})
                    titles.update(x.get("title","") for x in p.get("query",{}).get("search",[]) if file_name(x.get("title","")))
            except Exception as e:
                print(f"SEARCH_WARNING {topic} {phrase}: {str(e)[:120]}")
        rows=[]
        for i in range(0,min(len(titles),100),20):
            batch=sorted(titles)[i:i+20]
            try:
                j=api({"prop":"imageinfo","iiprop":"url|size|mime|sha1|extmetadata","titles":"|".join(batch)})
            except Exception as e:
                print(f"METADATA_WARNING {topic}: {str(e)[:120]}")
                continue
            for p in j.get("query",{}).get("pages",[]):
                ii=(p.get("imageinfo") or [{}])[0]
                license=(ii.get("extmetadata",{}).get("LicenseShortName") or {}).get("value","")
                if not (license.lower().startswith(("cc by ","cc0","public domain","pd-","pd ")) and "by-sa" not in license.lower()):continue
                if ii.get("mime") not in ("video/webm","video/ogg","application/ogg","video/mp4"):continue
                if not ii.get("url") or not ii.get("sha1") or int(ii.get("size",0))<100000:continue
                md=ii.get("extmetadata") or {}
                creator=html.unescape(re.sub("<[^>]*>"," ",(md.get("Artist") or {}).get("value",""))).strip()
                creator=re.sub(r"\s+"," ",creator)[:140]
                filename=p["title"][5:]
                rows.append({"assetTitle":filename,"sourcePage":"https://commons.wikimedia.org/wiki/File:"+quote(filename.replace(" ","_"),safe="()_-.'"),
                  "url":"https://commons.wikimedia.org/wiki/Special:FilePath/"+quote(filename,safe="()_-.'"),
                  "type":"video","author":creator,"license":license,
                  "license_url":(md.get("LicenseUrl") or {}).get("value",""),
                  "license_verified_at":"2026-10-31","size":ii["size"],"sha1":ii["sha1"],"original_url":ii["url"]})
        rows.sort(key=lambda x:(
          not bool(re.search({
            "mallard_duck":r"mallard|platyrhynchos|mlakarica",
            "eurasian_red_squirrel":r"sciurus vulgaris|red squirrel|veverica|eichhoernchen",
            "european_robin":r"erithacus rubecula|european robin|taščica",
            "domestic_goat":r"goats?\\b|capra hircus|nubian|vuohi",
            "rock_pigeon":r"columba livia|domestic pigeon|mestni golob|pigeons?"
          }[topic],x["assetTitle"],re.I)),
          x["size"]>120*1024*1024,x["size"]<1*1024*1024,
          len(x["assetTitle"]),x["assetTitle"]))
        result[topic]={"count":len(rows),"candidates":rows[:35]}
        print("TOPIC",topic,"FOUND",len(rows),"SHORTLIST",[(x["assetTitle"][:72],x["license"],x["size"]//1024//1024) for x in rows[:18]])
    Path("commons-discovery.json").write_text(json.dumps({"day":"2026-10-31","research_only":True,"topics":result},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":main()

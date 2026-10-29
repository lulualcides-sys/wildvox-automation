#!/usr/bin/env python3
"""Lightweight Commons video discovery: research only, never auto-publish."""
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API="https://commons.wikimedia.org/w/api.php"
UA="WildVoxSourceResearch/1.0 (GitHub QA; noncommercial research metadata)"
def query(params):
    p={"action":"query","format":"json","formatversion":2,**params}
    url=API+"?"+urlencode(p)
    with urlopen(Request(url,headers={"User-Agent":UA}),timeout=45) as r:
        return json.load(r)
def main():
    found={}
    categories=["Category:Videos of Calypte anna","Category:Videos of hummingbirds","Category:Calypte anna"]
    for cat in categories:
        cont={}
        for _ in range(3):
            j=query({"generator":"categorymembers","gcmtitle":cat,"gcmtype":"file","gcmlimit":100,"prop":"imageinfo","iiprop":"size",**cont})
            for p in j.get("query",{}).get("pages",[]):
                title=p.get("title","")
                if re.search(r"\\.(?:webm|ogv|ogg)$",title,re.I):
                    info=(p.get("imageinfo") or [{}])[0]
                    found[title]={"title":title,"size":info.get("size"),"category":cat}
            cont=j.get("continue") or {}
            if not cont:break
        time.sleep(.2)
    for phrase in ["Anna's hummingbird","Calypte anna"]:
        j=query({"list":"search","srsearch":phrase,"srnamespace":6,"srlimit":100})
        for p in j.get("query",{}).get("search",[]):
            title=p.get("title","")
            if re.search(r"\\.(?:webm|ogv|ogg)$",title,re.I):
                found.setdefault(title,{"title":title,"category":"search:"+phrase})
    rows=sorted(found.values(),key=lambda x:x["title"].lower())
    Path("commons-discovery.json").write_text(json.dumps({"subject":"Calypte anna","source_count":len(rows),"files":rows,"publication_hold":True},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"count":len(rows),"files":[x["title"] for x in rows]}))
if __name__=="__main__":main()

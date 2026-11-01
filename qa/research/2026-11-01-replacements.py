#!/usr/bin/env python3
"""One-pass replacement candidate poster frames; no media publishing."""
import base64, io, json, time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[2]
CAND=json.loads((ROOT/"qa/research/2026-11-01-replacement-candidates.json").read_text())
OUT=ROOT/"qa/research/replacement-previews"
OUT.mkdir(parents=True,exist_ok=True)
UA="WildVoxResearch/1.0 (licensed source thumbnail review)"
REPORT={}
def get(url):
    for i in range(2):
        try:
            with urlopen(Request(url,headers={"User-Agent":UA}),timeout=16) as r:
                return r.read()
        except Exception:
            if i==1: raise
            time.sleep(1)
for key,titles in CAND.items():
    u="https://commons.wikimedia.org/w/api.php?"+urlencode({
        "action":"query","format":"json","formatversion":"2",
        "prop":"imageinfo|categories","titles":"|".join("File:"+t for t in titles),
        "iiprop":"url|size|mime|extmetadata","iiurlwidth":320,
        "cllimit":"max"})
    pages=json.loads(get(u)).get("query",{}).get("pages",[])
    lookup={p.get("title","").casefold():p for p in pages}
    sheet=Image.new("RGB",(1280,480),"#101820")
    draw=ImageDraw.Draw(sheet)
    rows=[]
    for i,t in enumerate(titles):
        p=lookup.get(("File:"+t).casefold(),{})
        info=(p.get("imageinfo") or [{}])[0]
        m=info.get("extmetadata") or {}
        lic=(m.get("LicenseShortName") or {}).get("value","")
        artist=(m.get("Artist") or {}).get("value","")
        import re
        artist=re.sub("<[^>]*>","",artist).strip()
        cats="|".join(c.get("title","") for c in p.get("categories",[]))
        flag="license review needed" in cats.lower() or "copyright violations" in cats.lower()
        x,y=(i%4)*320,(i//4)*240
        ok=False
        try:
            thumb=info.get("thumburl")
            if not thumb:raise RuntimeError("No poster thumbnail")
            im=Image.open(io.BytesIO(get(thumb))).convert("RGB")
            im.thumbnail((310,188))
            sheet.paste(im,(x+(320-im.width)//2,y+4))
            ok=True
        except Exception as exc:
            draw.text((x+10,y+70),str(exc)[:34],fill="#ff6666")
        label=t[:37]+("..." if len(t)>37 else "")
        draw.text((x+4,y+198),str(i+1)+". "+label[:40],fill="#ffffff")
        draw.text((x+4,y+219),lic+" / "+artist[:20],fill="#aaccdd")
        rows.append({"title":t,"license":lic,"author":artist,"size":info.get("size"),
                     "duration":info.get("duration"),"width":info.get("width"),
                     "flagged":flag,"poster_ok":ok})
    jpg=OUT/(key+".jpg")
    sheet.save(jpg,"JPEG",quality=68,optimize=True)
    (OUT/(key+".b64")).write_text(base64.b64encode(jpg.read_bytes()).decode())
    REPORT[key]=rows
    print(key, "poster thumbnails",sum(z["poster_ok"] for z in rows),"/",len(rows),flush=True)
(OUT/"report.json").write_text(json.dumps(REPORT,indent=2))

#!/usr/bin/env python3
"""Commons poster-frame editorial contact sheets, not motion/behavior approval.

Only used on the isolated 2026-11-01 research branch. No media is published.
"""
import base64
import io
import json
import time
from pathlib import Path
from urllib.parse import urlencode, unquote, urlsplit
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
BATCH = json.loads((ROOT / "qa/research/2026-11-01-proposal.json").read_text())
OUT = ROOT / "qa/research/previews"
OUT.mkdir(parents=True, exist_ok=True)
UA = "WildVoxResearch/1.0 (editorial Commons source audit; no media publication)"
REPORT = {"day": "2026-11-01", "poster_frame_is_not_action_proof": True,
          "items": {}, "duplicate_sha1": [], "errors": []}
seen = {}

def fetch(url, timeout=35):
    req = Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    for attempt in range(3):
        try:
            with urlopen(req, timeout=timeout) as res:
                return res.read()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))

for key, entry in BATCH.items():
    titles = ["File:" + unquote(urlsplit(s["url"]).path.split("/Special:FilePath/")[-1]).replace("_", " ")
              for s in entry["sources"]]
    api = "https://commons.wikimedia.org/w/api.php?" + urlencode({
        "action": "query", "format": "json", "formatversion": "2",
        "titles": "|".join(titles), "prop": "imageinfo",
        "iiprop": "url|sha1|size|mime", "iiurlwidth": "320", "redirects": "1"
    })
    pages = json.loads(fetch(api)).get("query", {}).get("pages", [])
    lookup = {p.get("title", "").casefold(): p for p in pages}
    canvas = Image.new("RGB", (1280, 480), "#101820")
    draw = ImageDraw.Draw(canvas)
    for i, (title, src) in enumerate(zip(titles, entry["sources"])):
        col, row = i % 4, i // 4
        x, y = col * 320, row * 240
        p = lookup.get(title.casefold(), {})
        info = (p.get("imageinfo") or [{}])[0]
        sha1 = info.get("sha1")
        if sha1:
            if sha1 in seen:
                REPORT["duplicate_sha1"].append([seen[sha1], key + ":" + title])
            seen[sha1] = key + ":" + title
        record = {"title": title, "sha1": sha1, "size": info.get("size"),
                  "mime": info.get("mime"), "thumb_ok": False}
        thumb = info.get("thumburl")
        try:
            if not thumb:
                raise RuntimeError("Commons did not return a poster-frame thumbnail")
            raw = fetch(thumb, timeout=35)
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            img.thumbnail((310, 190))
            canvas.paste(img, (x + (320 - img.width) // 2, y + 5))
            record["thumb_ok"] = True
        except Exception as exc:
            record["preview_error"] = str(exc)[:180]
            REPORT["errors"].append(key + ":" + title + ": " + str(exc)[:150])
            draw.text((x + 10, y + 60), "PREVIEW UNAVAILABLE", fill="#ff7777")
        label = title[5:].replace(".webm", "").replace(".ogv", "")
        label = label[:39] + ("..." if len(label) > 39 else "")
        draw.text((x + 6, y + 197), f"{i+1}. {label[:39]}", fill="#ffffff")
        draw.text((x + 6, y + 217), src["license"] + " / " + src["author"][:23], fill="#a5c6e0")
        REPORT["items"].setdefault(key, []).append(record)
    jpg = OUT / (key + ".jpg")
    canvas.save(jpg, "JPEG", quality=65, optimize=True)
    (OUT / (key + ".b64")).write_text(base64.b64encode(jpg.read_bytes()).decode("ascii"))
    print(key, "previewed", sum(x["thumb_ok"] for x in REPORT["items"][key]), "/ 8")
(OUT / "report.json").write_text(json.dumps(REPORT, indent=2))
if REPORT["duplicate_sha1"]:
    raise SystemExit("FAIL: original Commons media SHA-1 reused: " + str(REPORT["duplicate_sha1"]))
print("Original Commons SHA1 unique across", len(seen), "assets.")
print("Poster frames are not evidence of movement, feeding or scene action.")

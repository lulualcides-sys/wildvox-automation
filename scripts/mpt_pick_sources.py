#!/usr/bin/env python3
"""Fill each batch candidate with licensed, never-used Commons videos.

Input candidates carry `commons_categories` (preferred: species-exact) and
optional `commons_search` queries. Output: same batch with `sources`
(6-12 widescreen CC0/PD/CC BY videos with author + license URL), never reusing
an original already on the media branch or picked for another video today.
Candidates that cannot reach MIN_SHOTS are dropped (fail closed, logged).
"""
import argparse
import re
import json
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scout_commons_portrait import (  # noqa: E402
    api, canonical_source, category_titles, previously_used, verify_titles,
)
from mpt_offline_render import MIN_SHOTS, MAX_SHOTS, is_widescreen  # noqa: E402


# Free-text Commons search pulled ads, cartoons, cooking and look-alike species
# on 18/11/2026. Only species categories are used now; titles are also screened.
JUNK = re.compile(r"trailer|nickrewind|rugrats|samsung|sora|openai|dvd|cook|recipe|cocer|receta|"
                  r"yummy|neon|mosaic|museo|museum|moth|cartoon|animation|anime|felix the cat|"
                  r"\(1[89]\d\d\)|episode|ep\. ?\d|show|music|official|commercial|advert|"
                  r"toy|plush|lego|game|minecraft|robot|drawing|painting|statue|sculpture|logo",
                  re.IGNORECASE)


def search_titles(query, limit=50, query_fn=api):
    r = query_fn({"action": "query", "list": "search", "srsearch": f"{query} filetype:video",
                  "srnamespace": "6", "srlimit": str(limit)})
    return [x["title"] for x in (r.get("query") or {}).get("search", [])]


def pixabay_search(q, pages=2):
    import os, time
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    key = os.environ.get("PIXABAY_API_KEY", "")
    if not key:
        raise RuntimeError("PIXABAY_API_KEY secret missing")
    hits = []
    for page in range(1, pages + 1):
        url = "https://pixabay.com/api/videos/?" + urlencode({
            "key": key, "q": q, "video_type": "film", "safesearch": "true",
            "per_page": 100, "page": page, "order": "popular"})
        with urlopen(Request(url, headers={"User-Agent": "WildVox/1.0"}), timeout=40) as r:
            body = json.load(r)
        hits += body.get("hits") or []
        if len(hits) >= int(body.get("totalHits") or 0):
            break
        time.sleep(1)
    return hits


def to_source(c):
    title = c["title"]
    if c.get("license") == "Pixabay Content License":
        return {"url": c["url"], "type": "video", "assetTitle": title, "sourcePage": c["sourcePage"],
                "author": c["author"], "license": c["license"], "license_url": c["license_url"],
                "width": c["width"], "height": c["height"], "tags": c.get("tags", "")}
    return {
        "url": "https://commons.wikimedia.org/wiki/Special:FilePath/" + quote(title),
        "type": "video",
        "assetTitle": title,
        "sourcePage": c["sourcePage"],
        "author": c["author"],
        "license": c["license"],
        "license_url": c["license_url"] or c["sourcePage"],
        "width": c["width"], "height": c["height"],
    }


def choose(candidates, used, want):
    """Widescreen, unused, highest resolution first; marks picks as used."""
    picks = []
    for c in sorted(candidates, key=lambda c: -(c["width"] * c["height"])):
        key = canonical_source(c["title"])
        if JUNK.search(c["title"]):
            continue
        if key in used or ("file:" + key) in used or not is_widescreen(c["width"], c["height"]) or c["width"] < 1280:
            continue
        used.update({key, "file:" + key, canonical_source(c.get("url", ""))})
        picks.append(to_source(c))
        if len(picks) >= want:
            break
    return picks


PIXABAY_BAD_TAGS = re.compile(r"cartoon|animation|animated|3d|render|illustration|toy|plush|food|"
                              r"cooking|neon|logo|drawing|painting|statue|costume|mask|cgi|moth|sushi|dish|market|"
                              r"carousel|fair|festival|cuttlefish|squid|shark|aquarium fish", re.I)


def pixabay_candidates(hits, required_tags):
    """Map Pixabay /api/videos hits to sources; only real-footage hits whose
    tags name the animal; largest widescreen rendition."""
    req = [t.lower() for t in required_tags]
    out = []
    for h in hits:
        tags = str(h.get("tags", "")).lower()
        lead = ", ".join(tags.split(", ")[:2])  # the animal must be a main subject
        if req and not any(t in lead for t in req):
            continue
        if PIXABAY_BAD_TAGS.search(tags) or h.get("type", "film") != "film":
            continue
        vids = h.get("videos") or {}
        best = None
        for size in ("large", "medium"):
            v = vids.get(size) or {}
            if v.get("url") and int(v.get("width") or 0) >= 1280:
                best = v
                break
        if not best or int(h.get("duration") or 0) < 4:
            continue
        out.append({
            "title": f"pixabay-{h['id']}.mp4",
            "sourcePage": h.get("pageURL") or f"https://pixabay.com/videos/id-{h['id']}/",
            "url": best["url"], "author": h.get("user") or "Pixabay",
            "license": "Pixabay Content License", "license_url": "https://pixabay.com/service/license-summary/",
            "width": int(best["width"]), "height": int(best["height"]), "tags": tags,
        })
    return out


def pick_batch(batch, used, gather):
    out, dropped = {}, {}
    for key, cand in batch.items():
        if cand.get("pixabay_queries"):
            pool = []
            for q in cand["pixabay_queries"]:
                pool += gather("pixabay", q)
            verified = pixabay_candidates(pool, cand.get("pixabay_required_tags") or [])
            want = int(cand.get("max_shots") or MAX_SHOTS)
            picks = choose(verified, used, min(want, MAX_SHOTS))
            if len(picks) < MIN_SHOTS:
                dropped[key] = f"only {len(picks)} usable Pixabay videos"
                for p in picks:
                    k = canonical_source(p["assetTitle"])
                    used.difference_update({k, "file:" + k})
                continue
            out[key] = dict(cand, sources=picks)
            continue
        titles = []
        for cat in cand.get("commons_categories") or []:
            titles += gather("category", cat)
        titles = list(dict.fromkeys(titles))
        verified = gather("verify", titles) if titles else []
        want = int(cand.get("max_shots") or MAX_SHOTS)
        picks = choose(verified, used, min(want, MAX_SHOTS))
        if len(picks) < MIN_SHOTS:
            dropped[key] = f"only {len(picks)} licensed unused widescreen videos"
            for p in picks:  # release picks so other candidates may use them
                k = canonical_source(p["assetTitle"])
                used.difference_update({k, "file:" + k})
            continue
        out[key] = dict(cand, sources=picks)
    return out, dropped


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True, type=Path)
    ap.add_argument("--media-dir", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    o = ap.parse_args(argv)
    batch = json.loads(o.batch.read_text(encoding="utf-8"))
    used = previously_used(o.media_dir)
    used |= {p.name.replace("_", " ").casefold() for p in o.media_dir.glob("*.webm")}

    def gather(kind, arg):
        if kind == "category":
            return category_titles(arg, limit=300)
        if kind == "search":
            return search_titles(arg)
        if kind == "pixabay":
            return pixabay_search(arg)
        return verify_titles(arg, set(), include_crop_review=True)

    out, dropped = pick_batch(batch, used, gather)
    o.output.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ready": list(out), "dropped": dropped}, ensure_ascii=False))
    if not out:
        sys.exit("No candidate has enough licensed unused footage")


if __name__ == "__main__":
    main()

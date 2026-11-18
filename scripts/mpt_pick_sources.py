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


def to_source(c):
    title = c["title"]
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


def pick_batch(batch, used, gather):
    out, dropped = {}, {}
    for key, cand in batch.items():
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
        return verify_titles(arg, set(), include_crop_review=True)

    out, dropped = pick_batch(batch, used, gather)
    o.output.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ready": list(out), "dropped": dropped}, ensure_ascii=False))
    if not out:
        sys.exit("No candidate has enough licensed unused footage")


if __name__ == "__main__":
    main()

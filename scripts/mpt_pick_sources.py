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
    ACCEPTED_LICENSE, api, author_text, canonical_source, category_titles, license_value,
    previously_used, verify_titles,
)
from mpt_offline_render import (  # noqa: E402
    MIN_PHOTOS, MIN_SHOTS, MAX_SHOTS, is_landscape_photo, is_widescreen,
)

MAX_PHOTOS = 8
RELATED_LABEL = "Imagens ilustrativas: espécies parentes"
INAT_LICENSES = {"cc0": ("CC0", "https://creativecommons.org/publicdomain/zero/1.0/"),
                 "cc-by": ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/")}


NOT_A_PHOTO = re.compile(r"engraving|illustration|drawing|lithograph|plate|painting|print|scan|map|"
                         r"skull|specimen|museum|taxiderm|diagram|stamp|book|page", re.I)


def commons_photo_candidates(pages):
    """Commons imageinfo pages -> licensed landscape photos of the exact species."""
    out = []
    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        if not str(info.get("mime", "")).startswith(("image/jpeg", "image/png")):
            continue
        ext = info.get("extmetadata") or {}
        if NOT_A_PHOTO.search(page.get("title", "") + " " + license_value(ext, "Categories")):
            continue
        lic = license_value(ext, "LicenseShortName")
        author = author_text(license_value(ext, "Artist"))
        if not ACCEPTED_LICENSE.fullmatch(lic) or not author:
            continue
        w, h = int(info.get("width") or 0), int(info.get("height") or 0)
        if w < 1200 or not is_landscape_photo(w, h):
            continue
        title = page["title"][5:]
        out.append({"type": "image", "title": title, "assetTitle": title,
                    "url": "https://commons.wikimedia.org/wiki/Special:FilePath/" + quote(title),
                    "sourcePage": info.get("descriptionurl") or "", "author": author, "license": lic,
                    "license_url": license_value(ext, "LicenseUrl") or info.get("descriptionurl"),
                    "width": w, "height": h})
    return [c for c in out if c["sourcePage"].startswith("https://commons.wikimedia.org/wiki/File:")]


def inat_photo_candidates(observations):
    """iNaturalist research-grade observations -> CC0/CC BY photos."""
    out = []
    for obs in observations:
        for ph in obs.get("photos") or []:
            code = str(ph.get("license_code") or "").lower()
            if code not in INAT_LICENSES:
                continue
            dims = ph.get("original_dimensions") or {}
            w, h = int(dims.get("width") or 0), int(dims.get("height") or 0)
            if w < 1200 or not is_landscape_photo(w, h) or not ph.get("url"):
                continue
            lic, lic_url = INAT_LICENSES[code]
            author = str((obs.get("user") or {}).get("name") or (obs.get("user") or {}).get("login") or "").strip()
            if not author:
                continue
            out.append({"type": "image", "title": f"inat-{ph['id']}.jpg", "assetTitle": f"inat-{ph['id']}.jpg",
                        "url": ph["url"].replace("/square.", "/original."),
                        "sourcePage": f"https://www.inaturalist.org/photos/{ph['id']}",
                        "author": author, "license": lic, "license_url": lic_url, "width": w, "height": h})
    return out


def choose_photos(candidates, used, want=MAX_PHOTOS):
    picks = []
    for c in sorted(candidates, key=lambda c: -(c["width"] * c["height"])):
        key = canonical_source(c["title"])
        if key in used or ("file:" + key) in used or JUNK.search(c["title"]):
            continue
        used.update({key, "file:" + key})
        picks.append({k: v for k, v in c.items() if k != "title"})
        if len(picks) >= want:
            break
    return picks


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


def commons_photo_search(species, limit=50):
    r = api({"action": "query", "generator": "search", "gsrsearch": f'"{species}" filetype:bitmap',
             "gsrnamespace": "6", "gsrlimit": str(limit), "prop": "imageinfo",
             "iiprop": "url|mime|size|extmetadata"})
    return commons_photo_candidates((r.get("query") or {}).get("pages", []))


def inat_search(species):
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    def get(path, params):
        url = "https://api.inaturalist.org/v1/" + path + "?" + urlencode(params)
        with urlopen(Request(url, headers={"User-Agent": "WildVox/1.0"}), timeout=40) as r:
            return json.load(r)
    taxa = get("taxa", {"q": species, "per_page": 5}).get("results") or []
    exact = [t for t in taxa if str(t.get("name", "")).lower() == species.lower()]
    if not exact:
        return []
    obs = get("observations", {"taxon_id": exact[0]["id"], "photo_license": "cc-by,cc0",
                               "quality_grade": "research", "photos": "true", "per_page": 60,
                               "order_by": "votes"}).get("results") or []
    return inat_photo_candidates(obs)


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
        if cand.get("pixabay_queries") or cand.get("species"):
            want = min(int(cand.get("max_shots") or MAX_SHOTS), MAX_SHOTS)
            def release(picks):
                for p in picks:
                    k = canonical_source(p["assetTitle"])
                    used.difference_update({k, "file:" + k})
            excl = set(cand.get("exclude_sources") or [])  # rejected in visual review
            # 1) real video of the exact animal
            pool = []
            for q in cand.get("pixabay_queries") or []:
                pool += gather("pixabay", q)
            vids = [c for c in pixabay_candidates(pool, cand.get("pixabay_required_tags") or [])
                    if c.get("sourcePage") not in excl]
            picks = choose(vids, used, want)
            if len(picks) >= MIN_SHOTS:
                out[key] = dict(cand, sources=picks, media_mode="video")
                continue
            release(picks)
            def photos_of(species):
                ph = [p for p in gather("inat_photos", species) if p["sourcePage"] not in excl]
                picks = choose_photos(ph, used)
                if len(picks) < MIN_PHOTOS:
                    release(picks)
                    picks = choose_photos(ph + [p for p in gather("commons_photos", species)
                                                if p["sourcePage"] not in excl], used)
                return picks
            # 2) licensed PHOTOS of the exact species (owner decision 18/11/2026)
            if cand.get("species"):
                picks = photos_of(cand["species"])
                if len(picks) >= MIN_PHOTOS:
                    c2 = dict(cand, sources=picks, media_mode="photo")
                    c2.pop("illustrative_label", None)  # exact species: no "related" label
                    out[key] = c2
                    continue
                release(picks)
            # 3) last resort: PHOTOS of named sister species (from the paper), labelled
            for rel in cand.get("related_species") or []:
                picks = photos_of(rel)
                if len(picks) >= MIN_PHOTOS:
                    out[key] = dict(cand, sources=picks, media_mode="related_photo",
                                    illustrative_label=RELATED_LABEL, related_used=rel)
                    break
                release(picks)
            if key in out:
                continue
            dropped[key] = "no exact video and too few photos of the species or its sister species"
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


def used_before_day(media_dir, day):
    """Sources used by earlier renders, ignoring this day's own renders (they get replaced)."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        for meta in media_dir.glob("*_meta.json"):
            if not meta.name.startswith(f"mpt_{day}_"):
                (Path(tmp) / meta.name).write_bytes(meta.read_bytes())
        return previously_used(Path(tmp))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True, type=Path)
    ap.add_argument("--media-dir", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    o = ap.parse_args(argv)
    batch = json.loads(o.batch.read_text(encoding="utf-8"))
    used = used_before_day(o.media_dir, o.batch.stem)
    used |= {p.name.replace("_", " ").casefold() for p in o.media_dir.glob("*.webm")}

    def gather(kind, arg):
        if kind == "category":
            return category_titles(arg, limit=300)
        if kind == "search":
            return search_titles(arg)
        if kind == "pixabay":
            return pixabay_search(arg)
        if kind == "commons_photos":
            return commons_photo_search(arg)
        if kind == "inat_photos":
            return inat_search(arg)
        return verify_titles(arg, set(), include_crop_review=True)

    out, dropped = pick_batch(batch, used, gather)
    o.output.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ready": list(out), "dropped": dropped}, ensure_ascii=False))
    if not out:
        sys.exit("No candidate has enough licensed unused footage")


if __name__ == "__main__":
    main()

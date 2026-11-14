#!/usr/bin/env python3
"""Scout ONLY *new*, license-eligible, portrait Wikimedia Commons videos.

Reports video candidates; cannot grant editorial/visual approval or modify
configs/daily.json. The original pages, video bytes and topic must be reviewed.
"""
import argparse
import html
import json
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, unquote, urlsplit
from urllib.request import Request, urlopen

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "WildVoxScientificVideoScouting/1.0 (GitHub: lulualcides-sys/wildvox-automation)"
CATEGORIES = [
    "Category:Videos of cats",
    "Category:Videos of playing cats",
    "Category:Videos of sleeping cats",
    "Category:Videos of grooming cats",
    "Category:Videos of kittens",
]
ACCEPTED_LICENSE = re.compile(
    r"^(?:CC0(?: 1\.0)?|CC BY (?:1\.0|2\.0|2\.5|3\.0|4\.0)|Public domain)$",
    re.IGNORECASE,
)


def api(params):
    url = API + "?" + urlencode(dict(params, format="json", formatversion="2"))
    for attempt in range(3):
        request = Request(url, headers={"User-Agent": USER_AGENT,
                                        "Accept": "application/json"})
        try:
            with urlopen(request, timeout=45) as response:
                payload = json.load(response)
            if payload.get("error"):
                raise RuntimeError("Commons API error: " + str(payload["error"]))
            return payload
        except (HTTPError, URLError) as exc:
            if attempt == 2:
                raise RuntimeError("Commons API request failed") from exc
            time.sleep(2 ** attempt)
    raise RuntimeError("Commons API unreachable")


def canonical_source(url):
    path = unquote(urlsplit(url or "").path)
    # Special:FilePath or direct upload URL can represent the same original.
    return path.rsplit("/", 1)[-1].replace("_", " ").casefold()


def previously_used(folder):
    """Read all old media metadata, not merely today's config."""
    used = set()
    for meta in folder.glob("*_meta.json"):
        try:
            body = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        sources = body.get("sources") or []
        if isinstance(sources, dict):
            sources = list(sources.values())
        if isinstance(sources, str):
            sources = [sources]
        if not isinstance(sources, list):
            continue
        for source in sources:
            # Historical media metadata uses both URL strings and maps.
            if isinstance(source, str):
                used.add(canonical_source(source))
            elif isinstance(source, dict):
                for name in ("url", "sourcePage", "assetTitle"):
                    value = source.get(name)
                    if isinstance(value, str) and value:
                        used.add(canonical_source(value))
    return used


def license_value(meta, key):
    obj = (meta or {}).get(key) or {}
    return str(obj.get("value") or "").strip()


def author_text(value):
    # This is display-only; Commons often embeds HTML attribution links.
    return html.unescape(re.sub(r"<[^>]+>", "", value or "")).strip()


def source_candidate(page, used):
    if not page.get("title", "").startswith("File:"):
        return None
    infos = page.get("imageinfo") or []
    if not infos:
        return None
    entry = infos[0]
    if not str(entry.get("mime") or "").startswith("video/"):
        return None
    ext = entry.get("extmetadata") or {}
    license_name = license_value(ext, "LicenseShortName")
    if not ACCEPTED_LICENSE.fullmatch(license_name):
        return None
    width, height = int(entry.get("width") or 0), int(entry.get("height") or 0)
    if width < 300 or height < 450:
        return None
    # The renderer's no-blur rule needs >=90% authentic sharp footage.
    portrait_fraction = min(
        (width / height) / (9 / 16), (9 / 16) / (width / height)
    )
    if portrait_fraction < .90:
        return None
    original = entry.get("url") or ""
    if not original or canonical_source(original) in used:
        return None
    author = author_text(license_value(ext, "Artist"))
    # Some video author fields are empty; never claim an attribution is cleared.
    if not author:
        return None
    source_page = entry.get("descriptionurl") or ""
    license_url = license_value(ext, "LicenseUrl")
    if not source_page.startswith("https://commons.wikimedia.org/"):
        return None
    if license_name.lower().startswith("cc by") and not license_url.startswith("https://"):
        return None
    return {
        "title": page["title"][5:],
        "sourcePage": source_page,
        "url": original,
        "author": author,
        "license": license_name,
        "license_url": license_url,
        "width": width,
        "height": height,
        "foreground_fraction": round(portrait_fraction, 3),
        "file_size": entry.get("size"),
        "source_status": "RESEARCH_ONLY_NOT_VISUALLY_APPROVED",
    }


def category_titles(category, limit=500):
    titles = []
    resume = None
    while len(titles) < limit:
        q = {"action": "query", "list": "categorymembers", "cmtitle": category,
             "cmtype": "file", "cmlimit": "100"}
        if resume:
            q["cmcontinue"] = resume
        response = api(q)
        titles.extend(x["title"] for x in
                      (response.get("query") or {}).get("categorymembers", [])
                      if x.get("title", "").startswith("File:"))
        resume = (response.get("continue") or {}).get("cmcontinue")
        if not resume:
            break
    return titles[:limit]


def search_cat_titles(max_results=250):
    seen = set()
    for category in CATEGORIES:
        try:
            seen.update(category_titles(category, limit=max_results))
        except RuntimeError as exc:
            print("Category unavailable:", category, str(exc), file=sys.stderr)
    return sorted(seen)[:max_results]


def verify_titles(titles, used):
    choices = []
    for start in range(0, len(titles), 30):
        response = api({"action": "query", "titles": "|".join(titles[start:start+30]),
                        "prop": "imageinfo",
                        "iiprop": "url|mime|size|extmetadata"})
        for page in (response.get("query") or {}).get("pages", []):
            candidate = source_candidate(page, used)
            if candidate:
                choices.append(candidate)
    return sorted(choices, key=lambda x: (-x["foreground_fraction"],
                                          x["file_size"] or 0, x["title"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--media-dir", default="media-branch")
    ap.add_argument("--output", default="commons_licensed_portrait_candidates.json")
    args = ap.parse_args()
    seen = previously_used(Path(args.media_dir))
    titles = search_cat_titles()
    matches = verify_titles(titles, seen)
    report = {
        "status": "RESEARCH_ONLY_NOT_EDITORIALLY_APPROVED",
        "source": "Wikimedia Commons live API",
        "searched_video_files": len(titles),
        "previously_used_original_filenames": len(seen),
        "new_eligible_portrait_sources": len(matches),
        "ready_to_render": False,
        "candidates": matches,
    }
    Path(args.output).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = Path(sys.argv[0]).name + ": " + str(len(matches)) + " candidates"
    print(summary)
    for entry in matches[:25]:
        print(json.dumps({k: entry[k] for k in (
            "title", "sourcePage", "license", "author", "width", "height",
            "foreground_fraction")}, ensure_ascii=False))
    if len(matches) < 8:
        print("BLOCK: fewer than 8 unreviewed eligible originals; do not render.")
    else:
        print("Sources found, but original pages and video frames still need manual review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

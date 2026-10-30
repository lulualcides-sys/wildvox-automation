#!/usr/bin/env python3
"""Fail closed on missing or noncommercial Wikimedia Commons video licenses.

The actual video bytes are downloaded/validated by the renderer after this
preflight. This script checks Commons' current API record for each source,
rather than trusting editorial license labels or a category listing.
"""
import argparse
import json
import sys
import time
from urllib.parse import quote, unquote, urlsplit, urlencode
from urllib.request import Request, urlopen

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "WildVoxEditorialAudit/1.0 (public GitHub project; source verification)"

def get_info(titles):
    query = urlencode({
        "action": "query", "format": "json", "formatversion": "2",
        "prop": "imageinfo|categories", "iiprop": "url|size|mime|extmetadata",
        "cllimit": "max", "clshow": "hidden",
        "titles": "|".join(titles), "redirects": "1"
    })
    request = Request(API + "?" + query, headers={
        "User-Agent": USER_AGENT, "Accept": "application/json"
    })
    for attempt in range(3):
        try:
            with urlopen(request, timeout=35) as response:
                payload = json.load(response)
            if payload.get("error"):
                raise RuntimeError("Commons API error: " + str(payload["error"])[:180])
            return payload.get("query", {}).get("pages", [])
        except Exception:
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))

def is_free_license(value):
    text = value.strip().lower().replace("_", " ")
    if "noncommercial" in text or "non-commercial" in text or "cc by-nc" in text or "no derivatives" in text:
        return False
    return text.startswith(("cc by ", "cc by-sa ", "cc0", "public domain", "pd-", "pd ", "cc zero"))

def validate_source_mix(batch):
    """Apply per-video quotas, not an arbitrary whole-batch video threshold.

    Five valid 6-video/2-photo candidates contain 30 videos, not 38.
    Photo-only exceptions require documentary evidence and >=3 real photos.
    The generator independently enforces the same source-count rules.
    """
    if len(batch) != 5:
        raise RuntimeError(f"Expected exactly 5 daily candidates, found {len(batch)}")
    video_total = 0
    for key, entry in batch.items():
        sources = entry.get("sources") or []
        exception = entry.get("trend_exception") or {}
        photo_exception = bool(exception.get("photo_only_allowed"))
        if photo_exception:
            if not exception.get("evidence_url") or not exception.get("evidence_published_date"):
                raise RuntimeError(f"{key}: photo-only exception lacks published evidence")
            if not 3 <= len(sources) <= 12:
                raise RuntimeError(f"{key}: photo-only exception needs 3-12 assets")
        elif not 8 <= len(sources) <= 12:
            raise RuntimeError(f"{key}: video-first candidate needs 8-12 assets")

        videos = sum(s.get("type", "video") == "video" for s in sources)
        images = sum(s.get("type", "video") == "image" for s in sources)
        if videos + images != len(sources):
            raise RuntimeError(f"{key}: unsupported media type in source pool")
        if photo_exception:
            if videos == 0 and images < 3:
                raise RuntimeError(f"{key}: photo-only exception requires >=3 photos")
        elif videos < 6 or videos > 10 or images > 2:
            raise RuntimeError(
                f"{key}: video-first pool requires 6-10 videos and <=2 photos "
                f"(found {videos} videos, {images} photos)"
            )
        video_total += videos
    return video_total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/daily.json")
    args = parser.parse_args()
    with open(args.config, encoding="utf-8") as handle:
        batch = json.load(handle)
    video_total = validate_source_mix(batch)
    requests = []
    for key, entry in batch.items():
        for source in entry.get("sources", []):
            media_type = source.get("type", "video")
            if not all(str(source.get(field) or "").strip() for field in ("author", "license", "license_url", "sourcePage")):
                raise RuntimeError(f"{key}: original creator, license, license URL and sourcePage must be documented before render: {source.get('url')}")
            if media_type not in ("video", "image"):
                raise RuntimeError(f"{key}: unsupported media type: {media_type}")
            url = source["url"]
            parsed = urlsplit(url)
            prefix = "/wiki/Special:FilePath/"
            if parsed.netloc != "commons.wikimedia.org" or not parsed.path.startswith(prefix):
                raise RuntimeError(f"{key}: unsupported source URL: {url}")
            filename = unquote(parsed.path[len(prefix):]).replace("_", " ")
            requests.append((key, source, "File:" + filename))
    checked = 0
    failures = []
    for offset in range(0, len(requests), 12):
        group = requests[offset:offset + 12]
        pages = get_info([title for _, _, title in group])
        by_title = {page.get("title", "").casefold(): page for page in pages}
        for key, source, title in group:
            page = by_title.get(title.casefold())
            if not page or page.get("missing") or not page.get("imageinfo"):
                failures.append(f"{key}: Commons asset missing: {title}")
                continue
            categories = {str(c.get("title") or "").casefold() for c in page.get("categories", [])}
            if any("license review needed" in c or "copyright violations" in c for c in categories):
                failures.append(f"{key}: Commons source is awaiting license review or flagged for copyright: {title}")
                continue
            info = page["imageinfo"][0]
            metadata = info.get("extmetadata") or {}
            license_name = str((metadata.get("LicenseShortName") or {}).get("value") or "")
            license_url = str((metadata.get("LicenseUrl") or {}).get("value") or "")
            # Commercial reuse alone does not prove that TikTok's delivery
            # terms can satisfy Creative Commons ShareAlike. Fail closed before
            # downloading/rendering an expensive batch. An independently
            # documented platform-compatible rights workflow is required before
            # any CC BY-SA source may be admitted.
            if "by-sa" in license_name.casefold():
                failures.append(
                    f"{key}: CC BY-SA/TikTok ShareAlike delivery compatibility "
                    f"not independently cleared; replace source: {title}"
                )
                continue
            if not is_free_license(license_name):
                failures.append(f"{key}: license not confirmed for commercial reuse: {title}: {license_name!r}")
                continue
            claimed_license = str(source.get("license") or "").casefold().replace(" ", "")
            verified_license = license_name.casefold().replace(" ", "")
            if claimed_license != verified_license:
                failures.append(f"{key}: config license does not match live Commons: {title}: {source.get('license')!r} vs {license_name!r}")
                continue
            mime = str(info.get("mime") or "").lower()
            expected = source.get("type", "video")
            video_mimes = ("video/webm", "video/ogg", "application/ogg", "video/mp4")
            image_mimes = ("image/jpeg", "image/png", "image/webp")
            if mime not in (video_mimes if expected == "video" else image_mimes):
                failures.append(f"{key}: not a {expected} asset: {title} ({mime})")
                continue
            if int(info.get("size") or 0) <= 100000 or not info.get("url"):
                failures.append(f"{key}: no downloadable media bytes: {title}")
                continue
            declared = str(source.get("license") or "")
            if declared and not is_free_license(declared):
                failures.append(f"{key}: nonfree license declared in config: {title}")
                continue
            print(f"OK {key}: {title} [{license_name}; {int(info['size'])} bytes; {license_url}]")
            checked += 1
    if failures:
        raise RuntimeError(f"{len(failures)} source(s) failed Commons audit:\\n" + "\\n".join(failures))
    print(f"Commons API preflight passed: {checked} authentic assets ({video_total} videos, {checked - video_total} images), all with commercial-reuse licenses and downloadable originals.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("SOURCE AUDIT FAILED: " + str(exc), file=sys.stderr)
        sys.exit(1)

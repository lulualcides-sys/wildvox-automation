"""Authentic Wikimedia Commons video transcodes for original-download failures.

Only Commons-hosted derivative encodings of the exact original file are allowed.
Never replace a failed wildlife clip with a different species or a still image.
"""
import json
from urllib.parse import unquote, urlencode, urlsplit
from urllib.request import Request, urlopen


def get_fallback_video_urls(original_url):
    parsed = urlsplit(original_url)
    prefix = "/wiki/Special:FilePath/"
    if parsed.scheme != "https" or parsed.netloc != "commons.wikimedia.org" or not parsed.path.startswith(prefix):
        return []
    filename = unquote(parsed.path[len(prefix):]).replace("_", " ")
    if not filename or "/" in filename or "\\\\" in filename or not filename.lower().endswith((".webm", ".ogv", ".mp4")):
        return []
    api = "https://commons.wikimedia.org/w/api.php?" + urlencode({
        "action": "query", "format": "json", "formatversion": 2,
        "prop": "videoinfo", "viprop": "derivatives", "titles": "File:" + filename,
    })
    try:
        with urlopen(Request(api, headers={"User-Agent": "WildVoxMediaFallback/1.0 (licensed Commons video derivative)"}), timeout=25) as response:
            payload = json.load(response)
    except (OSError, ValueError, KeyError):
        return []
    pages = payload.get("query", {}).get("pages", [])
    options = (pages[0].get("videoinfo") or [{}])[0].get("derivatives") or [] if pages else []
    candidates = []
    for option in options:
        url = str(option.get("src") or "")
        if url.startswith("//upload.wikimedia.org/"):
            url = "https:" + url
        p = urlsplit(url)
        try:
            width = int(option.get("width") or 0)
            height = int(option.get("height") or 0)
        except (TypeError, ValueError):
            continue
        if (p.scheme == "https" and p.netloc == "upload.wikimedia.org"
                and p.path.lower().endswith((".webm", ".ogv", ".mp4"))
                and 480 <= width <= 1280 and height >= 200):
            candidates.append((abs(width - 960), -width, url))
    candidates.sort()
    return [url for _, _, url in candidates[:2]]

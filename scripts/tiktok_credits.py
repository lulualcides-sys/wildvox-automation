"""Build traceable TikTok footage credits; NOT independent legal/editorial approval.

This is deliberately fail-closed: no abbreviated, missing or ShareAlike
attribution may silently pass into a publishable metadata caption.
"""
from urllib.parse import urlsplit

MAX_TIKTOK_CAPTION = 2200


def attributed_tiktok_caption(entry):
    caption = str(entry.get("caption") or "").strip()
    sources = entry.get("sources") or []
    if not caption:
        raise ValueError("TikTok caption is empty")
    if not 8 <= len(sources) <= 12:
        raise ValueError("TikTok footage credits require 8-12 actual sources")

    lines = []
    seen = set()
    for index, source in enumerate(sources, 1):
        author = str(source.get("author") or "").strip()
        license_name = str(source.get("license") or "").strip()
        license_url = str(source.get("license_url") or "").strip()
        source_page = str(source.get("sourcePage") or "").strip()
        original_url = str(source.get("url") or "").strip()
        if not all((author, license_name, license_url, source_page, original_url)):
            raise ValueError(f"Source {index}: missing creator, license or original URL")
        if "by-sa" in license_name.casefold().replace("_", "-"):
            raise ValueError(f"Source {index}: ShareAlike/TikTok compatibility not cleared")
        if not source_page.startswith("https://commons.wikimedia.org/wiki/File:"):
            raise ValueError(f"Source {index}: unsupported source credit URL")
        if urlsplit(license_url).scheme != "https":
            raise ValueError(f"Source {index}: invalid license URL")
        if original_url in seen:
            raise ValueError(f"Source {index}: duplicate footage URL")
        seen.add(original_url)
        # Include each original file, creator, license and license deed; even
        # footage by the same creator can represent different source works.
        lines.append(f"{index}. {author} | {license_name} | {source_page} | {license_url}")

    result = (caption + "\n\nFootage credits (edited: 9:16 crop, subtitles, narration):\n"
              + "\n".join(lines))
    if len(result) > MAX_TIKTOK_CAPTION:
        raise ValueError(
            f"Attribution caption is {len(result)} characters; TikTok limit "
            f"{MAX_TIKTOK_CAPTION}. Do not silently truncate legal credits."
        )
    return result

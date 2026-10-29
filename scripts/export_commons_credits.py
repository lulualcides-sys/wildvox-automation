#!/usr/bin/env python3
"""Extract original Wikimedia creator/credit/license metadata for independent review.

This is an audit artifact only: it never releases publication holds.
"""
import argparse
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from audit_commons_sources import get_info

class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)

def plain(value):
    p = TextOnly()
    p.feed(str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(" ".join(p.parts))).strip()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/daily.json")
    parser.add_argument("--output", default="commons-credits-report.json")
    args = parser.parse_args()
    batch = json.loads(Path(args.config).read_text(encoding="utf-8"))
    items = []
    for key, entry in batch.items():
        for i, source in enumerate(entry["sources"]):
            url = source["url"]
            p = urlsplit(url)
            prefix = "/wiki/Special:FilePath/"
            if p.netloc != "commons.wikimedia.org" or not p.path.startswith(prefix):
                raise ValueError(f"Unsupported Commons URL: {url}")
            title = "File:" + unquote(p.path[len(prefix):]).replace("_", " ")
            items.append((key, i, source, title))
    records = []
    for offset in range(0, len(items), 12):
        group = items[offset:offset + 12]
        pages = get_info([title for _, _, _, title in group])
        indexed = {page.get("title", "").casefold(): page for page in pages}
        for key, index, source, title in group:
            page = indexed.get(title.casefold())
            base = {"key": key, "index": index, "title": title,
                    "sourcePage": source.get("sourcePage"),
                    "config_author": source.get("author"),
                    "config_license": source.get("license")}
            if not page or not page.get("imageinfo"):
                records.append(dict(base, status="SOURCE_NOT_FOUND_IN_AUDIT"))
                continue
            metadata = page["imageinfo"][0].get("extmetadata") or {}
            field = lambda name: str((metadata.get(name) or {}).get("value") or "")
            artist = plain(field("Artist"))
            license_name = field("LicenseShortName")
            license_url = field("LicenseUrl")
            attribution = plain(field("Attribution"))
            credit = plain(field("Credit"))
            records.append(dict(base, status=("CREATOR_PRESENT_REVIEW_REQUIRED" if artist else "MISSING_CREATOR"),
                                artist=artist, artist_html=field("Artist"),
                                credit=credit, attribution=attribution,
                                commons_license=license_name, commons_license_url=license_url,
                                license_match=(not source.get("license") or
                                               source["license"].lower().replace(" ", "") ==
                                               license_name.lower().replace(" ", ""))))
    result = {"editorial_day": "2026-10-29", "config": args.config,
              "scope": "Original Commons API Artist/Credit/Attribution/License fields; HTML normalized for human review; not final legal clearance",
              "source_count": len(records),
              "missing_creator_count": sum(x["status"] == "MISSING_CREATOR" for x in records),
              "unverified_config_author_count": sum(not x["config_author"] for x in records),
              "records": records, "publication_hold": True}
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("source_count", "missing_creator_count", "unverified_config_author_count")}))
    if len(records) != len(items):
        raise RuntimeError("Incomplete creator audit")
if __name__ == "__main__":
    main()

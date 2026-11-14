#!/usr/bin/env python3
"""Search NEW authentic Commons cat videos outside fixed categories, without approval.

Only metadata research. Uses Wikimedia's namespaced search API and the existing
CC0/PD/CC BY + historical dedupe filters. Every result remains unreviewed.
"""
import argparse
import json
import sys
from pathlib import Path

from scout_commons_portrait import (
    api, previously_used, verify_titles, CommonsRateLimited
)

QUERIES = (
    "cat filetype:video",
    "kitten filetype:video",
    "gato filetype:video",
)
MAX_TOTAL = 200


def search_titles(queries=QUERIES, per_query=50, query_fn=api):
    if not 1 <= per_query <= 100 or len(queries) > 5:
        raise ValueError("Query budget exceeded")
    titles = set()
    counts = {}
    for query in queries:
        response = query_fn({
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srnamespace": "6",
            "srlimit": str(per_query),
            "srprop": "",
        })
        matches = (response.get("query") or {}).get("search") or []
        local = {
            match["title"]
            for match in matches
            if isinstance(match, dict)
            and isinstance(match.get("title"), str)
            and match["title"].startswith("File:")
        }
        counts[query] = len(local)
        titles.update(local)
    return sorted(titles)[:MAX_TOTAL], counts


def run(media_dir, query_fn=api, verifier=verify_titles):
    used = previously_used(Path(media_dir))
    status, blocker, sources, examined, count = (
        "RESEARCH_ONLY_NOT_EDITORIALLY_APPROVED", None, [], 0, {}
    )
    try:
        titles, count = search_titles(query_fn=query_fn)
        examined = len(titles)
        sources = verifier(titles, used, include_crop_review=True)
    except CommonsRateLimited as exc:
        blocker = str(exc)
        status = "BLOCKED_EXTERNAL_COMMONS_HTTP_429"
    except RuntimeError as exc:
        blocker = str(exc)
        status = "BLOCKED_EXTERNAL_SOURCE_SEARCH"
    return {
        "status": status,
        "technical_blocker": blocker,
        "source": "Wikimedia Commons Search API, namespace File: (6)",
        "searched_video_files": examined,
        "search_matches_by_query": count,
        "previously_used_original_filenames": len(used),
        "new_eligible_portrait_sources": sum(
            not x["crop_review_required"] for x in sources
        ),
        "new_crop_review_only_sources": sum(
            x["crop_review_required"] for x in sources
        ),
        "ready_to_render": False,
        "curiosity_fact_sheet_verified": False,
        "visual_independent_approval": False,
        "candidates": sources,
    }


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--media-dir", default="media-branch")
    cli.add_argument("--output", default="commons_keyword_sources.json")
    opts = cli.parse_args()
    report = run(opts.media_dir)
    Path(opts.output).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    print(json.dumps({
        "status": report["status"],
        "queried": report["search_matches_by_query"],
        "prospects": len(report["candidates"]),
        "ready_to_render": False,
    }, ensure_ascii=False))
    # HTTP 429 is an external blocker, not permission to publish.
    return 0 if report["status"].startswith("RESEARCH_ONLY") else 2


if __name__ == "__main__":
    sys.exit(main())

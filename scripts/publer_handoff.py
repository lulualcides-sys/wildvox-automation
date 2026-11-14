#!/usr/bin/env python3
"""Send an independently APPROVED WildVox clip to a GitHub Issue -> Publer Zap.

Issue title = direct MP4 URL; issue body = full licensed TikTok caption.
Never reports a created GitHub issue as a Publer/TikTok scheduled or published post.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

REPO = "lulualcides-sys/wildvox-automation"
LABEL = "wildvox-publer-ready"
TZ = ZoneInfo("America/Sao_Paulo")
SLOTS = [(10, 5), (12, 40), (16, 10), (19, 35), (22, 5)]


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def config_fingerprint(entry):
    body = json.dumps(entry, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def next_slot(now):
    for hour, minute in SLOTS:
        slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if slot > now + timedelta(minutes=30):
            return slot
    return None


def valid_receipt(receipt, key, entry, meta, media_sha, media_blob, now):
    checks = receipt.get("editorial_checks") or {}
    return (
        receipt.get("day_local") == now.date().isoformat()
        and receipt.get("candidate_key") == key
        and receipt.get("revision") == entry.get("revision")
        and receipt.get("decision") == "APPROVE"
        and receipt.get("publication_hold") is True
        and receipt.get("network") == "tiktok"
        and receipt.get("account") == "@wildvox"
        and receipt.get("config_sha256") == meta.get("config_sha256")
        and receipt.get("media_sha256") == media_sha
        and receipt.get("git_blob_mp4") == media_blob
        and isinstance(receipt.get("github_actions_run_id"), int)
        and isinstance(receipt.get("github_original_zip_artifact_id"), int)
        and checks.get("curiosity_first") is True
        and checks.get("verified_biological_mechanism") is True
        and checks.get("comparison_or_consequence") is True
        and checks.get("non_descriptive_story") is True
        and checks.get("visual_quality_approved") is True
        and isinstance(checks.get("independent_original_zip_inspection"), str)
        and len(checks["independent_original_zip_inspection"]) >= 30
    )


def review_receipt(folder, key, entry, meta, media_sha, media_blob, now):
    matched = []
    for path in folder.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if data.get("candidate_key") != key:
            continue
        if valid_receipt(data, key, entry, meta, media_sha, media_blob, now):
            matched.append(str(path))
    if len(matched) != 1:
        raise RuntimeError(
            f"{key}: expected exactly ONE current-day, exact-hash, "
            f"independently inspected APPROVE receipt; found {len(matched)}"
        )
    return matched[0]


def prepare(key, config, media_dir, reviews, now):
    if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
        raise RuntimeError("Invalid candidate key")
    entry = config.get(key)
    if not isinstance(entry, dict) or not str(entry.get("revision", "")).startswith(now.date().isoformat()):
        raise RuntimeError("Only current-day factual videos can be handed to Publer")
    if entry.get("publication_hold") is not True:
        raise RuntimeError("Keep publication_hold=true; only an independent receipt can authorize one MP4")
    if entry.get("language") != "pt-BR" or entry.get("voice") != "pm_alex":
        raise RuntimeError("Unsupported narration: require pt-BR/pm_alex")
    sources = entry.get("sources") or []
    sheet = entry.get("curiosity_fact_sheet") or {}
    if len(sources) < 8 or len(sheet.get("fact_sources") or []) < 2:
        raise RuntimeError("Missing licensed real footage or scientific facts")
    mp4 = media_dir / f"{key}.mp4"
    meta_path = media_dir / f"{key}_meta.json"
    review = media_dir / f"{key}_review.jpg"
    if any(not p.is_file() or not p.stat().st_size for p in (mp4, meta_path, review)):
        raise RuntimeError("Canonical MP4, metadata or review sheet missing")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if (meta.get("key") != key or meta.get("title") != entry.get("title")
            or meta.get("publication_hold") is not True
            or meta.get("config_sha256") != config_fingerprint(entry)
            or meta.get("sources") != sources
            or meta.get("language") != "pt-BR" or meta.get("voice") != "pm_alex"):
        raise RuntimeError("Rendered metadata is inconsistent with today's editorial config")
    if not 30 <= float(meta.get("duration") or 0) <= 45:
        raise RuntimeError("Outside 30–45s duration")
    caption = meta.get("caption") or ""
    if not caption.strip() or len(caption) > 2200:
        raise RuntimeError("Missing full caption or TikTok length exceeded")
    if any((source.get("sourcePage") or "") not in caption for source in sources):
        raise RuntimeError("Source credits missing from TikTok caption")
    media_sha = sha256_file(mp4)
    media_blob = subprocess.check_output(["git", "hash-object", str(mp4)], text=True).strip()
    receipt = review_receipt(reviews, key, entry, meta, media_sha, media_blob, now)
    slot = next_slot(now)
    if slot is None:
        raise RuntimeError("No authorized future local publishing slots")
    url = f"https://raw.githubusercontent.com/{REPO}/media/{key}.mp4"
    return {"title": url, "body": caption, "key": key, "receipt": receipt,
            "sha256": media_sha, "next_slot": slot.isoformat()}


def github(method, endpoint, token, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(f"https://api.github.com/repos/{REPO}{endpoint}", data=data,
                  headers={"Authorization": f"Bearer {token}",
                           "Accept": "application/vnd.github+json",
                           "Content-Type": "application/json"}, method=method)
    with urlopen(req, timeout=40) as response:
        return json.load(response)


def create_handoff(issue, token):
    # The GitHub issue label is also the Zapier New Issue trigger filter.
    # Check all issue states; a closed handoff must never be dispatched again.
    existing = github("GET", f"/issues?state=all&labels={LABEL}&per_page=100", token)
    if any(i.get("title") == issue["title"] for i in existing):
        raise RuntimeError("Duplicate Publer handoff: exact media URL already queued")
    return github("POST", "/issues", token,
                  {"title": issue["title"], "body": issue["body"],
                   "labels": [LABEL]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", required=True)
    parser.add_argument("--config", default="configs/daily.json")
    parser.add_argument("--media-dir", default="media-branch")
    parser.add_argument("--reviews", default="qa/reviews")
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()
    now = datetime.now(TZ)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    item = prepare(args.key, config, Path(args.media_dir), Path(args.reviews), now)
    if not args.send:
        print(json.dumps({"eligible": True, "dry_run": True,
                          "key": item["key"], "sha256": item["sha256"],
                          "next_slot": item["next_slot"]}))
        return
    if os.getenv("WILDVOX_PUBLER_ENABLED") != "true":
        raise SystemExit("Publer bridge is not connected/enabled; no issue sent")
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GitHub token is unavailable")
    result = create_handoff(item, token)
    print(json.dumps({"handoff_issue_url": result.get("html_url"),
                      "key": item["key"], "published": False,
                      "publer_post_id": None, "next_slot_hint": item["next_slot"]}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Schedule the current, freshly rendered WildVox Daily 5 batch via Buffer.

Requirements:
  - GitHub Actions secret BUFFER_API_KEY
  - Connected TikTok channel @wildvox in Buffer
  - Github Actions variable WILDVOX_BUFFER_ENABLED=true
No credentials are written to this repository.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

API_URL = "https://api.buffer.com"
REPO = "lulualcides-sys/wildvox-automation"
TZ = ZoneInfo("America/Sao_Paulo")
SLOTS = [(10, 5), (12, 40), (16, 10), (19, 35), (22, 5)]
MAX_PENDING_FREE = 10


def utc_datetime(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def get_json(url):
    headers = {"User-Agent": "WildVox-automation/1.0", "Accept": "application/vnd.github+json"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    with urlopen(Request(url, headers=headers), timeout=35) as resp:
        return json.load(resp)


def graphql(query, variables=None):
    token = os.getenv("BUFFER_API_KEY")
    if not token:
        raise RuntimeError(
            "GitHub Actions secret BUFFER_API_KEY is missing. "
            "Set the secret in the repository Settings > Secrets and variables > Actions."
        )
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    request = Request(
        API_URL,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
        method="POST",
    )
    for attempt in range(3):
        try:
            with urlopen(request, timeout=45) as response:
                response_json = json.load(response)
            if response_json.get("errors"):
                raise RuntimeError("Buffer GraphQL error: " + str(response_json["errors"])[:500])
            return response_json.get("data") or {}
        except HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 ** attempt * 4)
                continue
            raise RuntimeError("Buffer API returned HTTP " + str(exc.code)) from None
        except URLError as exc:
            if attempt < 2:
                time.sleep(2 ** attempt * 4)
                continue
            raise RuntimeError("Buffer API network request failed") from None
    raise RuntimeError("Buffer API did not respond successfully")


def normalize_caption(caption):
    """Buffer/TikTok permits up to five hashtags; preserve the #WildVox tag."""
    tags = re.findall(r"(?<!\w)#[\w]+", caption)
    if len(tags) > 5:
        kept = tags[:4]
        brand = next((tag for tag in tags if tag.lower() == "#wildvox"), None)
        if brand and brand not in kept:
            kept.append(brand)
        else:
            kept.append(tags[4])
        pieces = caption.split()
        result = []
        seen = set()
        for piece in pieces:
            if piece.startswith("#"):
                if piece in kept and piece not in seen:
                    result.append(piece)
                    seen.add(piece)
            else:
                result.append(piece)
        caption = " ".join(result)
    if not caption.strip() or len(caption) > 2200:
        raise RuntimeError("Caption is empty or exceeds TikTok's 2,200 character limit")
    return caption.strip()


def sha256_entry(entry):
    normalized = json.dumps(entry, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def check_fresh_render(config, media_root, now):
    today = now.strftime("%Y-%m-%d")
    if len(config) != 5:
        raise RuntimeError("Daily config must contain exactly five video entries")
    if any(entry.get("publication_hold") for entry in config.values()):
        raise RuntimeError("Editorial preparation hold: TikTok scheduling is not authorized for this batch")
    expected = {}
    for key, entry in config.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            raise RuntimeError("Invalid media key: " + key)
        if not str(entry.get("revision", "")).startswith(today):
            raise RuntimeError("Stale daily config for " + key + "; no older videos will be scheduled")
        files = [media_root / (key + suffix) for suffix in (".mp4", "_meta.json", "_review.jpg")]
        if not all(f.is_file() and f.stat().st_size > 0 for f in files):
            raise RuntimeError("Missing canonical rendered asset(s) for " + key)
        metadata = json.loads(files[1].read_text(encoding="utf-8"))
        if metadata.get("key") != key or metadata.get("title") != entry.get("title"):
            raise RuntimeError("Video metadata does not match daily config: " + key)
        if metadata.get("caption") != entry.get("caption"):
            raise RuntimeError("Video caption does not match daily config: " + key)
        if metadata.get("sources") != entry.get("sources"):
            raise RuntimeError("Media sources differ from daily config: " + key)
        duration = float(metadata.get("duration") or 0)
        if not (float(entry.get("min_duration") or 0) <= duration <= float(entry.get("max_duration") or 0)):
            raise RuntimeError("Invalid video duration: " + key)
        expected[key] = {
            "caption": normalize_caption(entry["caption"]),
            "url": "https://raw.githubusercontent.com/" + REPO + "/media/" + key + ".mp4",
            "digest": sha256_entry(entry),
        }
    return expected


def verify_recent_daily_run(now):
    """An old batch re-rendered today must never count as newly prepared content."""
    commits = get_json("https://api.github.com/repos/" + REPO + "/commits?path=configs/daily.json&per_page=1")
    if not commits:
        raise RuntimeError("Could not verify the latest daily config commit")
    config_commit_at = utc_datetime(commits[0]["commit"]["committer"]["date"])
    if config_commit_at.astimezone(TZ).date() != now.date():
        raise RuntimeError("Today's daily video configuration has not been committed")
    url = "https://api.github.com/repos/" + REPO + "/actions/workflows/wildvox-daily.yml/runs?per_page=10"
    runs = get_json(url).get("workflow_runs", [])
    if not any(
        run.get("conclusion") == "success"
        and utc_datetime(run["created_at"]) >= config_commit_at
        and utc_datetime(run["created_at"]).astimezone(TZ).date() == now.date()
        for run in runs
    ):
        raise RuntimeError("There is no successful Daily 5 render after today's config change")


def find_tiktok_channel():
    data = graphql("query { account { organizations { id name } } }")
    candidates = []
    for org in data["account"]["organizations"]:
        q = "query { channels(input:{organizationId:" + json.dumps(org["id"]) + "}) { id name displayName service isQueuePaused isDisconnected isLocked } }"
        channels = graphql(q).get("channels") or []
        for channel in channels:
            if str(channel.get("service", "")).lower() != "tiktok":
                continue
            names = " ".join(str(channel.get(k) or "") for k in ("name", "displayName")).lower()
            if "wildvox" in names:
                candidates.append((org["id"], channel))
    if len(candidates) != 1:
        raise RuntimeError(
            "Expected exactly one connected TikTok @wildvox channel in Buffer; found "
            + str(len(candidates)) + ". Connect @wildvox in Buffer first."
        )
    org_id, channel = candidates[0]
    if channel["isDisconnected"] or channel["isLocked"] or channel["isQueuePaused"]:
        raise RuntimeError("TikTok @wildvox channel is disconnected, locked or paused")
    return org_id, channel["id"]


def read_existing_posts(org_id, channel_id):
    posts = []
    after = None
    for _ in range(8):  # up to 400 posts, enough for normal 30-day operation
        after_arg = "" if not after else ", after: " + json.dumps(after)
        query = (
            "query { posts(first:50" + after_arg
            + ", input:{ organizationId:" + json.dumps(org_id)
            + ", filter:{channelIds:[" + json.dumps(channel_id)
            + "],status:[scheduled,sent,error]} })"
            + " { edges { node { id text dueAt status channelId } }"
            + " pageInfo { hasNextPage endCursor } } }"
        )
        result = graphql(query)["posts"]
        posts.extend(edge["node"] for edge in result["edges"])
        page = result["pageInfo"]
        if not page["hasNextPage"]:
            return posts
        after = page["endCursor"]
        if not after:
            raise RuntimeError("Buffer pagination ended unexpectedly")
    raise RuntimeError("Too many Buffer posts to verify duplicates safely")


def validate_public_url(url):
    # GitHub raw files must be available publicly until Buffer completes publishing.
    req = Request(url, method="HEAD", headers={"User-Agent": "WildVox-automation/1.0"})
    try:
        with urlopen(req, timeout=45) as response:
            if response.status != 200:
                raise RuntimeError("Media URL is not publicly accessible")
    except (HTTPError, URLError) as exc:
        raise RuntimeError("Public video asset cannot be fetched: " + url) from None


def schedule_video(channel_id, caption, media_url, due_at):
    mutation = """
    mutation CreateWildVoxPost($input: CreatePostInput!) {
      createPost(input: $input) {
        __typename
        ... on PostActionSuccess { post { id status dueAt text channelId } }
        ... on MutationError { message }
      }
    }"""
    data = graphql(mutation, {
        "input": {
            "channelId": channel_id,
            "text": caption,
            "schedulingType": "automatic",
            "mode": "customScheduled",
            "dueAt": due_at.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "assets": [{"video": {"url": media_url, "metadata": {"thumbnailOffset": 2000}}}],
            "metadata": {"tiktok": {"isAiGenerated": True}},
            "aiAssisted": True,
        }
    })
    item = data["createPost"]
    if item["__typename"] != "PostActionSuccess":
        raise RuntimeError("Buffer refused post: " + str(item.get("message", item["__typename"])))
    post = item["post"]
    if not post.get("id"):
        raise RuntimeError("Buffer response did not include a new post ID")
    return post


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--media-dir", default="media-branch")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    now = datetime.now(TZ)
    cfg = json.loads(Path("configs/daily.json").read_text(encoding="utf-8"))
    batch = check_fresh_render(cfg, Path(args.media_dir), now)
    verify_recent_daily_run(now)
    if args.dry_run:
        print("DRY RUN: today's five media candidates passed freshness/duration/file checks; no posts created")
        return

    org_id, channel_id = find_tiktok_channel()
    posts = read_existing_posts(org_id, channel_id)
    scheduled = [p for p in posts if p.get("status") == "scheduled"]
    if len(scheduled) > MAX_PENDING_FREE:
        raise RuntimeError("Buffer Free scheduled queue already exceeds its limit")
    captions_seen = {p.get("text", "").strip() for p in posts if p.get("status") in ("scheduled", "sent", "error")}
    open_slots = [
        now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        for hour, minute in SLOTS
    ]
    open_slots = [slot for slot in open_slots if slot > now + timedelta(minutes=10)]
    used_slots = {
        utc_datetime(p["dueAt"]).astimezone(TZ).replace(second=0, microsecond=0)
        for p in scheduled if p.get("dueAt")
    }
    open_slots = [slot for slot in open_slots if slot not in used_slots]
    queued = 0
    already = 0
    for key, item in batch.items():
        caption = item["caption"]
        if caption in captions_seen:
            print("Already scheduled/sent (or failed and needs review): " + key)
            already += 1
            continue
        if not open_slots:
            raise RuntimeError("No future TikTok slots remain today; no unsafe late posting")
        if len(scheduled) + queued >= MAX_PENDING_FREE:
            raise RuntimeError("Buffer Free queue is full; cannot schedule remaining WildVox videos")
        slot = open_slots.pop(0)
        validate_public_url(item["url"])
        post = schedule_video(channel_id, caption, item["url"], slot)
        print("Scheduled " + key + " for " + slot.isoformat() + " | Buffer post ID: " + post["id"])
        queued += 1
        captions_seen.add(caption)
    print("DONE: " + str(queued) + " new Buffer schedules; " + str(already) + " existing; total daily batch 5")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Never include API tokens in logs, exceptions, or public files.
        print("WildVox Buffer integration failed: " + str(exc), file=sys.stderr)
        sys.exit(1)

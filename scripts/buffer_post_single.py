#!/usr/bin/env python3
"""Schedule ONE user-approved WildVox MP4 on Buffer (TikTok @wildvox).

Reuses the guarded helpers of publish_buffer.py (exact @wildvox channel,
duplicate-caption check, free-queue limit, public URL check). Credits list
only the Commons sources actually used in the render.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_buffer as pb  # noqa: E402

MAX_CAPTION = 2200


def credited_caption(entry: dict, exclude_pages=()) -> str:
    caption = str(entry.get("caption") or "").strip()
    if not caption:
        raise ValueError("Caption is empty")
    used = [s for s in entry.get("sources") or [] if s.get("sourcePage") not in set(exclude_pages)]
    if not used:
        raise ValueError("No sources to credit")
    lines, seen = [], set()
    for i, s in enumerate(used, 1):
        fields = [str(s.get(k) or "").strip() for k in ("author", "license", "license_url", "sourcePage", "url")]
        author, lic, lic_url, page, url = fields
        if not all(fields):
            raise ValueError(f"Source {i}: missing creator/license/URL")
        if "by-sa" in lic.casefold().replace("_", "-"):
            raise ValueError(f"Source {i}: ShareAlike not cleared for TikTok")
        if not page.startswith("https://commons.wikimedia.org/wiki/File:") or urlsplit(lic_url).scheme != "https":
            raise ValueError(f"Source {i}: invalid credit URL")
        if url in seen:
            raise ValueError(f"Source {i}: duplicate footage")
        seen.add(url)
        lines.append(f"{i}. {author} | {lic} | {page} | {lic_url}")
    text = caption + "\n\nCréditos dos vídeos (edição vertical 9:16 sem corte, legendas e narração):\n" + "\n".join(lines)
    if len(text) > MAX_CAPTION:
        raise ValueError(f"Caption {len(text)} chars exceeds TikTok limit; not truncating credits")
    if caption.count("#") > 5:
        raise ValueError("Buffer/TikTok: max 5 hashtags")
    return text


def next_slot(now, used_slots):
    for day in range(0, 3):
        base = now + timedelta(days=day)
        for h, m in pb.SLOTS:
            slot = base.replace(hour=h, minute=m, second=0, microsecond=0)
            if slot > now + timedelta(minutes=15) and slot not in used_slots:
                return slot
    raise RuntimeError("No free slot in the next 3 days")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("--media-url", required=True)
    ap.add_argument("--exclude-source", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    o = ap.parse_args(argv)
    if not o.media_url.startswith("https://raw.githubusercontent.com/lulualcides-sys/wildvox-automation/media/"):
        raise RuntimeError("Media must come from the public WildVox media branch")

    entry = json.loads(Path("configs/daily.json").read_text(encoding="utf-8"))[o.key]
    caption = credited_caption(entry, o.exclude_source)
    now = datetime.now(pb.TZ)

    org_id, channel_id = pb.find_tiktok_channel()
    posts = pb.read_existing_posts(org_id, channel_id)
    scheduled = [p for p in posts if p.get("status") == "scheduled"]
    if len(scheduled) >= pb.MAX_PENDING_FREE:
        raise RuntimeError("Buffer Free queue is full (10)")
    if any(p.get("text", "").strip() == caption.strip() for p in posts):
        print("Already scheduled/sent/error in Buffer; not posting twice: " + o.key)
        return
    used = {pb.utc_datetime(p["dueAt"]).astimezone(pb.TZ).replace(second=0, microsecond=0)
            for p in scheduled if p.get("dueAt")}
    slot = next_slot(now, used)
    pb.validate_public_url(o.media_url)
    print(json.dumps({"key": o.key, "slot": slot.isoformat(), "caption_chars": len(caption)}, ensure_ascii=False))
    if o.dry_run:
        print("DRY RUN: nothing scheduled")
        return
    post = pb.schedule_video(channel_id, caption, o.media_url, slot)
    print(f"SCHEDULED {o.key} at {slot.isoformat()} | Buffer post ID: {post['id']} | status: {post.get('status')}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("WildVox single Buffer post failed: " + str(exc), file=sys.stderr)
        sys.exit(1)

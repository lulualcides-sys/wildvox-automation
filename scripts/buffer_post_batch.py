#!/usr/bin/env python3
"""Schedule every rendered video of a daily MPT batch on Buffer (TikTok).

Reads <meta-dir>/<key>.json (written by the render job: caption, used
sources, media URL). Each video gets the next free WildVox slot; never posts a
caption twice; stops at the Buffer Free queue limit.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_buffer as pb  # noqa: E402
from buffer_post_single import credited_caption, find_channel, next_slot  # noqa: E402

# Daily MPT batch: 7 slots (America/Sao_Paulo) so >=5 videos/day fit the same day.
DAILY_SLOTS = [(10, 5), (12, 40), (14, 25), (16, 10), (19, 35), (21, 5), (22, 35)]
MEDIA_PREFIX = "https://raw.githubusercontent.com/lulualcides-sys/wildvox-automation/media/"


def load_metas(meta_dir: Path, order: list) -> list:
    metas = []
    for key in order:
        f = meta_dir / f"{key}.json"
        if not f.is_file():
            print(f"SKIP {key}: no successful render", flush=True)
            continue
        m = json.loads(f.read_text(encoding="utf-8"))
        if not str(m.get("media_url", "")).startswith(MEDIA_PREFIX):
            raise RuntimeError(f"{key}: media must be on the public WildVox media branch")
        metas.append(m)
    return metas


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True, type=Path)
    ap.add_argument("--meta-dir", required=True, type=Path)
    ap.add_argument("--tiktok-handle", required=True)
    ap.add_argument("--dry-run", action="store_true")
    o = ap.parse_args(argv)
    order = list(json.loads(o.batch.read_text(encoding="utf-8")))
    metas = load_metas(o.meta_dir, order)
    if not metas:
        raise RuntimeError("Nothing rendered; nothing to post")

    org_id, channel_id = find_channel(o.tiktok_handle)
    posts = pb.read_existing_posts(org_id, channel_id)
    scheduled = [p for p in posts if p.get("status") == "scheduled"]
    seen = {p.get("text", "").strip() for p in posts}
    used = {pb.utc_datetime(p["dueAt"]).astimezone(pb.TZ).replace(second=0, microsecond=0)
            for p in scheduled if p.get("dueAt")}
    now = datetime.now(pb.TZ)
    queued = 0
    for m in metas:
        caption = credited_caption({"caption": m["caption"], "sources": m["sources"]})
        if caption.strip() in seen:
            print(f"ALREADY {m['key']}: caption exists in Buffer")
            continue
        if len(scheduled) + queued >= pb.MAX_PENDING_FREE:
            print(f"STOP: Buffer Free queue full; {m['key']} not scheduled")
            break
        slot = next_slot(now, used, DAILY_SLOTS)
        pb.validate_public_url(m["media_url"])
        if o.dry_run:
            print(f"DRY {m['key']} -> {slot.isoformat()}")
        else:
            post = pb.schedule_video(channel_id, caption, m["media_url"], slot)
            print(f"SCHEDULED {m['key']} at {slot.isoformat()} | Buffer post ID: {post['id']}")
        used.add(slot)
        seen.add(caption.strip())
        queued += 1
    print(f"DONE: {queued} scheduled of {len(metas)} rendered ({len(order)} planned)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("WildVox batch Buffer post failed: " + str(exc), file=sys.stderr)
        sys.exit(1)

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
    pixabay = [s for s in used if s.get("license") == "Pixabay Content License"
               and str(s.get("sourcePage", "")).startswith("https://pixabay.com/")]
    if len(pixabay) == len(used):
        # Pixabay Content License: no attribution required; we still disclose the source.
        text = caption + "\n\nVídeos: Pixabay (Pixabay Content License). Narração e edição: WildVox."
        if len(text) > MAX_CAPTION or caption.count("#") > 5:
            raise ValueError("Caption too long or more than 5 hashtags")
        return text
    used = [s for s in used if s not in pixabay]
    lines, seen = [], set()
    for i, s in enumerate(used, 1):
        fields = [str(s.get(k) or "").strip() for k in ("author", "license", "license_url", "sourcePage", "url")]
        author, lic, lic_url, page, url = fields
        if not all(fields):
            raise ValueError(f"Source {i}: missing creator/license/URL")
        if "by-sa" in lic.casefold().replace("_", "-"):
            raise ValueError(f"Source {i}: ShareAlike not cleared for TikTok")
        if not (page.startswith("https://commons.wikimedia.org/wiki/File:") or page.startswith("https://www.inaturalist.org/photos/")) \
                or urlsplit(lic_url).scheme != "https":
            raise ValueError(f"Source {i}: invalid credit URL")
        if url in seen:
            raise ValueError(f"Source {i}: duplicate footage")
        seen.add(url)
        lines.append(f"{i}. {author} | {lic} | {page} | {lic_url}")
    text = caption + "\n\nCréditos das imagens (edição vertical 9:16 sem corte, legendas e narração):\n" + "\n".join(lines)
    if len(text) > MAX_CAPTION:
        # Compact TASL credits: title (Commons file), author, license; each
        # license deed URL listed once. Still names every used work.
        short, deeds = [], {}
        for i, s in enumerate(used, 1):
            title = str(s.get("assetTitle") or s["sourcePage"].rsplit("File:", 1)[-1])
            where = "iNaturalist" if "inaturalist.org" in s["sourcePage"] else "Commons"
            short.append(f"{i}. {s['author']} ({s['license']}) – {where}: {title}")
            deeds.setdefault(s["license"], s["license_url"])
        text = (caption + "\n\nCréditos (Wikimedia Commons/iNaturalist; editado: 9:16, legendas, narração):\n"
                + "\n".join(short) + "\nLicenças: " + " ".join(f"{k} {v}" for k, v in deeds.items()))
    if len(text) > MAX_CAPTION:
        raise ValueError(f"Caption {len(text)} chars exceeds TikTok limit; not truncating credits")
    if caption.count("#") > 5:
        raise ValueError("Buffer/TikTok: max 5 hashtags")
    return text


def find_channel(handle: str):
    """Exact TikTok handle match only (owner confirmed @wildvox6 on 18/11/2026)."""
    handle = handle.strip().lower().lstrip("@")
    ok_links = {"", f"https://tiktok.com/@{handle}", f"https://www.tiktok.com/@{handle}"}
    found = []
    for org in pb.graphql("query { account { organizations { id } } }")["account"]["organizations"]:
        q = ("query { channels(input:{organizationId:" + json.dumps(org["id"])
             + "}) { id name externalLink service isQueuePaused isDisconnected isLocked } }")
        for c in pb.graphql(q).get("channels") or []:
            if (str(c.get("service", "")).lower() == "tiktok"
                    and str(c.get("name") or "").strip().lower().lstrip("@") == handle
                    and str(c.get("externalLink") or "").strip().lower().rstrip("/") in ok_links):
                found.append((org["id"], c))
    if len(found) != 1:
        raise RuntimeError(f"Expected exactly one TikTok @{handle} channel in Buffer; found {len(found)}")
    org_id, c = found[0]
    if c["isDisconnected"] or c["isLocked"] or c["isQueuePaused"]:
        raise RuntimeError(f"TikTok @{handle} is disconnected, locked or paused")
    return org_id, c["id"]


def next_slot(now, used_slots, slots=None, days=3):
    for day in range(0, days):
        base = now + timedelta(days=day)
        for h, m in (slots or pb.SLOTS):
            slot = base.replace(hour=h, minute=m, second=0, microsecond=0)
            if slot > now + timedelta(minutes=15) and slot not in used_slots:
                return slot
    raise RuntimeError(f"No free slot in the next {days} days")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("--media-url", required=True)
    ap.add_argument("--exclude-source", action="append", default=[])
    ap.add_argument("--tiktok-handle", required=True, help="exact Buffer TikTok handle, e.g. wildvox6")
    ap.add_argument("--dry-run", action="store_true")
    o = ap.parse_args(argv)
    if not o.media_url.startswith("https://raw.githubusercontent.com/lulualcides-sys/wildvox-automation/media/"):
        raise RuntimeError("Media must come from the public WildVox media branch")

    entry = json.loads(Path("configs/daily.json").read_text(encoding="utf-8"))[o.key]
    caption = credited_caption(entry, o.exclude_source)
    now = datetime.now(pb.TZ)

    org_id, channel_id = find_channel(o.tiktok_handle)
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

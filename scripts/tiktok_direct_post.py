#!/usr/bin/env python3
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import requests

API_BASE = "https://open.tiktokapis.com"
MAX_CHUNK = 32 * 1024 * 1024
MAX_UPLOAD_CHUNK = 64 * 1024 * 1024
MIN_CHUNK = 5 * 1024 * 1024


def fail(message):
    raise SystemExit(message)


def api_json(response, label):
    try:
        payload = response.json()
    except Exception:
        fail(f"{label}: invalid JSON response ({response.status_code})")
    if not response.ok:
        fail(f"{label}: HTTP {response.status_code}: {payload}")
    err = payload.get("error") or {}
    code = err.get("code")
    if code and code != "ok":
        fail(f"{label}: TikTok error {code}: {err.get('message', '')}")
    return payload


def refresh_access_token():
    direct = os.getenv("TIKTOK_ACCESS_TOKEN")
    if direct:
        return direct

    client_key = os.getenv("TIKTOK_CLIENT_KEY")
    client_secret = os.getenv("TIKTOK_CLIENT_SECRET")
    refresh_token = os.getenv("TIKTOK_REFRESH_TOKEN")
    if not all([client_key, client_secret, refresh_token]):
        fail(
            "TikTok credentials missing. Set TIKTOK_ACCESS_TOKEN, or "
            "TIKTOK_CLIENT_KEY + TIKTOK_CLIENT_SECRET + TIKTOK_REFRESH_TOKEN."
        )

    r = requests.post(
        f"{API_BASE}/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    payload = api_json(r, "refresh token")
    token = payload.get("access_token")
    if not token:
        fail("refresh token: access_token missing in TikTok response")

    rotated = payload.get("refresh_token")
    if rotated and rotated != refresh_token:
        print(
            "WARNING: TikTok rotated the refresh token. Persist the new refresh token "
            "in your server-side secret store before the next refresh.",
            file=sys.stderr,
        )
    return token


def creator_info(access_token):
    r = requests.post(
        f"{API_BASE}/v2/post/publish/creator_info/query/",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json={},
        timeout=30,
    )
    payload = api_json(r, "creator info")
    return payload.get("data") or {}


def choose_chunks(size):
    if size <= MAX_UPLOAD_CHUNK:
        return size, 1
    chunk = MAX_CHUNK
    count = size // chunk
    if count < 1:
        count = 1
    if count > 1000:
        fail("video is too large for TikTok chunk limits")
    final_size = size - chunk * (count - 1)
    if final_size > 128 * 1024 * 1024:
        fail("final TikTok upload chunk would exceed 128 MB")
    if final_size < MIN_CHUNK:
        fail("invalid TikTok chunk plan: final chunk below 5 MB")
    return chunk, count


def init_post(access_token, video_path, caption, privacy, is_aigc):
    size = video_path.stat().st_size
    chunk_size, total_chunk_count = choose_chunks(size)
    body = {
        "post_info": {
            "title": caption,
            "privacy_level": privacy,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "brand_content_toggle": False,
            "brand_organic_toggle": False,
            "is_aigc": is_aigc,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunk_count,
        },
    }
    r = requests.post(
        f"{API_BASE}/v2/post/publish/video/init/",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json=body,
        timeout=30,
    )
    payload = api_json(r, "initialize direct post")
    data = payload.get("data") or {}
    if not data.get("publish_id") or not data.get("upload_url"):
        fail("initialize direct post: publish_id/upload_url missing")
    return data, chunk_size, total_chunk_count


def upload_chunks(upload_url, video_path, chunk_size, total_chunk_count):
    size = video_path.stat().st_size
    with video_path.open("rb") as fh:
        start = 0
        for index in range(total_chunk_count):
            if index == total_chunk_count - 1:
                length = size - start
            else:
                length = chunk_size
            data = fh.read(length)
            if len(data) != length:
                fail("unexpected EOF while reading video")
            end = start + length - 1
            r = requests.put(
                upload_url,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Length": str(length),
                    "Content-Range": f"bytes {start}-{end}/{size}",
                },
                data=data,
                timeout=180,
            )
            expected = 201 if index == total_chunk_count - 1 else 206
            if r.status_code != expected:
                fail(
                    f"upload chunk {index + 1}/{total_chunk_count}: "
                    f"expected HTTP {expected}, got {r.status_code}: {r.text[:500]}"
                )
            start = end + 1


def fetch_status(access_token, publish_id):
    r = requests.post(
        f"{API_BASE}/v2/post/publish/status/fetch/",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json={"publish_id": publish_id},
        timeout=30,
    )
    payload = api_json(r, "fetch post status")
    return payload.get("data") or {}


def load_caption(meta_path):
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    caption = (meta.get("caption") or "").strip()
    title = (meta.get("title") or "").strip()
    if not caption:
        caption = title
    if not caption:
        fail("metadata has no caption/title")
    return caption


def main():
    parser = argparse.ArgumentParser(
        description="Publish one WildVox video through TikTok Content Posting API."
    )
    parser.add_argument("--video", required=True)
    parser.add_argument("--meta", required=True)
    parser.add_argument(
        "--privacy",
        default="SELF_ONLY",
        choices=[
            "PUBLIC_TO_EVERYONE",
            "MUTUAL_FOLLOW_FRIENDS",
            "FOLLOWER_OF_CREATOR",
            "SELF_ONLY",
        ],
    )
    parser.add_argument("--caption-override", default="")
    parser.add_argument("--consent", action="store_true")
    parser.add_argument("--not-aigc", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=180)
    args = parser.parse_args()

    if not args.consent:
        fail(
            "Explicit publish consent is required. Re-run with --consent only after "
            "reviewing the creator, privacy setting, caption, and video."
        )

    video_path = Path(args.video)
    meta_path = Path(args.meta)
    if not video_path.is_file():
        fail(f"video not found: {video_path}")
    if not meta_path.is_file():
        fail(f"metadata not found: {meta_path}")

    access_token = refresh_access_token()
    creator = creator_info(access_token)
    print(
        json.dumps(
            {
                "creator_username": creator.get("creator_username"),
                "creator_nickname": creator.get("creator_nickname"),
                "privacy_level_options": creator.get("privacy_level_options"),
                "max_video_post_duration_sec": creator.get("max_video_post_duration_sec"),
            },
            ensure_ascii=False,
        )
    )

    options = creator.get("privacy_level_options") or []
    if args.privacy not in options:
        fail(
            f"privacy {args.privacy} is not allowed for this creator; "
            f"available={options}"
        )

    audited = os.getenv("TIKTOK_AUDITED", "").lower() in {"1", "true", "yes"}
    if args.privacy == "PUBLIC_TO_EVERYONE" and not audited:
        fail(
            "PUBLIC_TO_EVERYONE blocked locally because TIKTOK_AUDITED is not true. "
            "Unaudited TikTok Direct Post clients are restricted to private posting."
        )

    caption = args.caption_override.strip() or load_caption(meta_path)
    data, chunk_size, total_chunks = init_post(
        access_token,
        video_path,
        caption,
        args.privacy,
        is_aigc=not args.not_aigc,
    )
    publish_id = data["publish_id"]
    upload_chunks(data["upload_url"], video_path, chunk_size, total_chunks)

    deadline = time.time() + max(0, args.poll_seconds)
    last = None
    while time.time() <= deadline:
        last = fetch_status(access_token, publish_id)
        status = last.get("status")
        if status in {"PUBLISH_COMPLETE", "FAILED"}:
            break
        time.sleep(10)

    print(
        json.dumps(
            {
                "publish_id": publish_id,
                "status": (last or {}).get("status"),
                "fail_reason": (last or {}).get("fail_reason"),
                "public_post_ids": (last or {}).get("publicaly_available_post_id", []),
            },
            ensure_ascii=False,
        )
    )
    if (last or {}).get("status") == "FAILED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

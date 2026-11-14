#!/usr/bin/env python3
"""Render genuine Commons video-frame contact sheets for independent crop review.

This tool cannot approve footage, create a production batch or publish. It
uses actual downloaded original videos and requires the 100%-real source view.
"""
import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


PREFERRED = (
    "Cat discovers it was being spied on.webm",
    "Fur Lickers.webm",
    "2022-10-18 LJUBLJANA Doma CARNIVORA Felis catus DOMAČA MAČKA 4.webm",
    "Fox Dark - Cat (2017).webm",
    "2022-10-18 LJUBLJANA Doma CARNIVORA Felis catus DOMAČA MAČKA 2.webm",
    "35 удивительных трюков от Бенгальского кота (без звука).webm",
    "Interaction between a peacock and a cat.webm",
    "Gato escalando.webm",
    "2024-02-04 Micro. Silly Sleeping-1Bx7ivngEIg.webm",
    "Wie kam die Katze zum Menschen?.webm",
    "Dierenasyl.webm",
)
MAX_BYTES = 60 * 1024 * 1024


def selected(candidates):
    by_name = {item["title"]: item for item in candidates}
    result = []
    for title in PREFERRED:
        info = by_name.get(title)
        if not info or info.get("source_status") not in (
                "RESEARCH_ONLY_NOT_VISUALLY_APPROVED",
                "RESEARCH_ONLY_REQUIRES_VISUAL_CROP_REVIEW"):
            continue
        if (info.get("file_size") or 0) > MAX_BYTES:
            continue
        if urlsplit(info.get("url", "")).hostname != "upload.wikimedia.org":
            continue
        if not info.get("sourcePage", "").startswith("https://commons.wikimedia.org/"):
            continue
        result.append(info)
    return result


def download_source(url, path, limit=MAX_BYTES):
    if urlsplit(url).hostname != "upload.wikimedia.org":
        raise ValueError("Unexpected download host")
    for attempt in range(2):
        try:
            req = Request(url, headers={"User-Agent": "WildVoxFootagePreview/1.0 (research)"})
            with urlopen(req, timeout=80) as response, open(path, "wb") as out:
                if int(response.headers.get("Content-Length") or 0) > limit:
                    raise ValueError("Source exceeds max download bytes")
                total = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > limit:
                        raise ValueError("Actual source exceeded max bytes")
                    out.write(chunk)
            return
        except HTTPError as exc:
            if exc.code != 429 or attempt:
                raise
            time.sleep(10)


def probe_duration(video):
    raw = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video)], text=True)
    return float(raw.strip())


def real_frame(video, second, output):
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(second),
         "-i", str(video), "-frames:v", "1", "-y", str(output)],
        check=True, timeout=65, capture_output=True)


def centered_portrait(frame):
    """This is a PREVIEW only; it never approves the center crop."""
    w, h = frame.size
    desired = 9 / 16
    if w / h > desired:
        crop_w = round(h * desired)
        return frame.crop(((w-crop_w)//2, 0, (w-crop_w)//2+crop_w, h))
    crop_h = round(w / desired)
    return frame.crop((0, (h-crop_h)//2, w, (h-crop_h)//2+crop_h))


def contact_sheet(info, source, output):
    # Pillow only needed by the isolated preview workflow, not QA unit imports.
    from PIL import Image, ImageDraw
    dur = probe_duration(source)
    if dur < 4:
        raise ValueError("Source too short to assess a multi-shot clip")
    times = [round(min(max(dur - .5, .1), t), 2) for t in (0.8, 2.8, 4.8, 7.0)]
    sheet = Image.new("RGB", (1160, 4 * 390 + 110), "#111111")
    painter = ImageDraw.Draw(sheet)
    painter.text((12, 8), info["title"][:118], fill="white")
    painter.text((12, 28), "License: " + info["license"] +
                 " | ORIGINAL LEFT, SIMULATED CENTER CROP RIGHT | NOT APPROVED", fill="white")
    painter.text((12, 48), info["sourcePage"][:160], fill="white")
    with tempfile.TemporaryDirectory() as td:
        for idx, stamp in enumerate(times):
            jpeg = Path(td) / f"frame{idx}.png"
            real_frame(source, stamp, jpeg)
            with Image.open(jpeg) as raw:
                frame = raw.convert("RGB")
            portrait = centered_portrait(frame)
            y = 95 + idx * 390
            left = frame.copy()
            left.thumbnail((565, 350))
            portrait.thumbnail((565, 350))
            sheet.paste(left, (8 + (565-left.width)//2, y))
            sheet.paste(portrait, (590 + (565-portrait.width)//2, y))
            painter.text((8, y+352), f"Source {stamp}s", fill="white")
            painter.text((590, y+352), f"Unapproved 9:16 center crop {stamp}s", fill="white")
    sheet.save(output, quality=86, optimize=True)
    return {"duration": round(dur, 2), "times": times, "preview": output.name}


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--research", required=True)
    cli.add_argument("--out", default="crop-preview")
    cli.add_argument("--count", type=int, default=11)
    args = cli.parse_args()
    research = json.loads(Path(args.research).read_text(encoding="utf-8"))
    if research.get("status") != "RESEARCH_ONLY_NOT_EDITORIALLY_APPROVED":
        raise SystemExit("No reliable current research list; no preview or render")
    out = Path(args.out)
    out.mkdir(exist_ok=True, parents=True)
    results = []
    for idx, item in enumerate(selected(research["candidates"])[:args.count], 1):
        filename = out / f"original_{idx}.webm"
        jpeg = out / f"source_{idx:02d}_crop_contact.jpg"
        result = {"title": item["title"], "sourcePage": item["sourcePage"],
                  "author": item["author"], "license": item["license"],
                  "url": item["url"], "crop_review_required": item["crop_review_required"],
                  "visual_approved": False, "status": "UNREVIEWED"}
        try:
            download_source(item["url"], filename)
            details = contact_sheet(item, filename, jpeg)
            result.update(details)
            result["status"] = "PREVIEW_GENERATED_NEEDS_INDEPENDENT_INSPECTION"
        except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError,
                subprocess.TimeoutExpired) as error:
            result["error"] = str(error)[:300]
            result["status"] = "FAILED_NO_APPROVAL"
            jpeg.unlink(missing_ok=True)
        finally:
            filename.unlink(missing_ok=True)  # Archive review JPEG, not raw megabytes.
        print(f"{idx}: {result['status']} {item['title'][:64]}", flush=True)
        results.append(result)
    report = {"status": "REAL_VIDEO_PREVIEW_ONLY", "editorially_approved": False,
              "ready_to_render": False, "items": results}
    (out / "contact_sheets_review_pending.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"succeeded": sum(x["status"].startswith("PREVIEW") for x in results),
                      "failed": sum(x["status"].startswith("FAILED") for x in results),
                      "ready_to_render": False}))


if __name__ == "__main__":
    main()

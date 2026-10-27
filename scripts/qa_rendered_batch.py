#!/usr/bin/env python3
"""WildVox rendered-MP4 technical QA; never grants editorial approval."""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def normalize(text):
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9']+", " ", str(text))).strip().lower()


def probe(path):
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,width,height", "-of", "json", str(path)],
        capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


def freeze_durations(path):
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-vf",
         "scale=180:-2,freezedetect=n=-45dB:d=1.0", "-an", "-f", "null", "-"],
        capture_output=True, text=True, check=True)
    return [float(s) for s in re.findall(
        r"lavfi\.freezedetect\.freeze_duration:\s*([0-9.]+)", p.stderr)]


def inspect(config, directory, day):
    errors, records, urls = [], [], set()
    if len(config) != 5:
        errors.append(f"Expected exactly five videos, got {len(config)}")
    for key, cfg in config.items():
        item = {"key": key, "revision": cfg.get("revision"), "errors": []}
        bad = item["errors"]
        video = directory / f"{key}.mp4"
        meta_path = directory / f"{key}_meta.json"
        review = directory / f"{key}_review.jpg"
        for path in (video, meta_path, review):
            if not path.is_file() or path.stat().st_size == 0:
                bad.append(f"Missing or empty artifact: {path.name}")
        if not str(cfg.get("revision") or "").startswith(day):
            bad.append("Stale editorial revision")
        if cfg.get("publication_hold") is not True:
            bad.append("publication_hold must remain true until separate visual approval")
        blocks = cfg.get("visual_plan") or []
        if not 5 <= len(blocks) <= 7 or normalize(
                " ".join(b.get("text", "") for b in blocks)) != normalize(cfg.get("script", "")):
            bad.append("visual_plan must cover full script in 5-7 spoken blocks")
        sources = cfg.get("sources") or []
        if not 8 <= len(sources) <= 12 or sum(
                s.get("type", "video") == "video" for s in sources) < 6:
            bad.append("8-12 assets and >=6 genuine videos required")
        for s in sources:
            url = s.get("url")
            if not url or url in urls:
                bad.append(f"Duplicate/missing URL: {url}")
            urls.add(url)
            if not all(s.get(k) for k in ("author", "license", "license_url", "sourcePage")):
                bad.append(f"Incomplete credits: {s.get('assetTitle', url)}")
        if video.is_file():
            try:
                data = probe(video)
                duration = float(data["format"]["duration"])
                item["duration"] = round(duration, 3)
                streams = data.get("streams", [])
                images = [s for s in streams if s["codec_type"] == "video"]
                if not 30 <= duration <= 45:
                    bad.append(f"Duration {duration:.3f}s outside 30-45s")
                if not any(s["codec_type"] == "audio" for s in streams):
                    bad.append("Missing narration audio")
                if not images or (images[0].get("width"), images[0].get("height")) != (1080, 1920):
                    bad.append("Incorrect 1080x1920 portrait format")
                item["freeze_durations"] = freeze_durations(video)
                if any(d > 1.0 for d in item["freeze_durations"]):
                    bad.append(f"Freeze >1.0s: {item['freeze_durations']}")
            except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as exc:
                bad.append(f"ffprobe/freezedetect failure: {exc}")
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                timeline = meta.get("narration_timeline") or []
                if len(timeline) != len(blocks):
                    bad.append("Rendered Kokoro block count mismatch")
                else:
                    cursor = 0.0
                    for expected, actual in zip(blocks, timeline):
                        if normalize(expected["text"]) != normalize(actual.get("text", "")):
                            bad.append("Rendered narration differs from visual_plan")
                        if abs(float(actual["start"]) - cursor) > 0.1:
                            bad.append("Kokoro block boundaries are not contiguous")
                        cursor = float(actual["end"])
                    if "duration" in item and abs(cursor - item["duration"]) > 0.2:
                        bad.append("Kokoro audio length differs from MP4")
            except (OSError, ValueError, TypeError, KeyError) as exc:
                bad.append(f"Metadata error: {exc}")
        errors.extend(f"{key}: {msg}" for msg in bad)
        records.append(item)
    return {"editorial_day": day, "technical_pass": not errors,
            "editorial_approved": False, "publication_hold": True,
            "videos": records, "errors": errors}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/daily.json")
    ap.add_argument("--media-dir", default="public")
    ap.add_argument("--report", default="technical_qa_report.json")
    ap.add_argument("--date")
    args = ap.parse_args()
    day = args.date or datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    report = inspect(config, Path(args.media_dir), day)
    Path(args.report).write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for item in report["videos"]:
        print(item["key"], item.get("duration"), "PASS" if not item["errors"] else "FAIL",
              item["errors"], flush=True)
    print("Technical QA:", "PASS (not editorial approval)" if report["technical_pass"] else "FAIL")
    return 0 if report["technical_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

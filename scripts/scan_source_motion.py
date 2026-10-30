#!/usr/bin/env python3
"""Find authentic moving source windows without rendering or claiming editorial approval."""
import argparse
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

# 2026-10-30: inspect genuine source windows before changing the editorial
# batch. This research-only workflow does not render or authorize posting.
TARGETS = (
    ("common_kingfisher_nest_tunnel", 0),
    ("common_kingfisher_nest_tunnel", 3),
    ("bald_eagle_feeding_eaglets", 5),
    ("european_mantis_two_jobs", 4),
)

ALTERNATES = {
    ("red_fox_hunt_to_play", 9): {
        "assetTitle": "Red fox (Vulpes vulpes) and her pups.webm",
        "url": "https://commons.wikimedia.org/wiki/Special:FilePath/Red%20fox%20(Vulpes%20vulpes)%20and%20her%20pups.webm",
        "sourcePage": "https://commons.wikimedia.org/wiki/File:Red_fox_(Vulpes_vulpes)_and_her_pups.webm",
        "author": "Timo Newton-Syms",
        "license": "CC BY-SA 2.0; Flickr license reviewed 2015",
        "start_seconds": 0,
    },
    ("red_fox_hunt_to_play", 10): {
        "assetTitle": "Red fox kits playing.webm",
        "url": "https://commons.wikimedia.org/wiki/Special:FilePath/Red%20fox%20kits%20playing.webm",
        "sourcePage": "https://commons.wikimedia.org/wiki/File:Red_fox_kits_playing.webm",
        "author": "Rhododendrites",
        "license": "CC BY-SA 4.0; self-published featured Commons media",
        "start_seconds": 0,
    },
    ("red_fox_hunt_to_play", 8): {
        "assetTitle": "Red fox pups playing along Owens Bay Nature Trail (53369021529).webm",
        "url": "https://commons.wikimedia.org/wiki/Special:FilePath/Red%20fox%20pups%20playing%20along%20Owens%20Bay%20Nature%20Trail%20(53369021529).webm",
        "sourcePage": "https://commons.wikimedia.org/wiki/File:Red_fox_pups_playing_along_Owens_Bay_Nature_Trail_(53369021529).webm",
        "author": "USFWS Mountain Prairie",
        "license": "Public domain (US federal government, USFWS); verify before use",
        "start_seconds": 0,
    },
}
WINDOW = 5.0
FPS = 8


def call(cmd, timeout=150):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout, check=True)


def duration(path):
    x = call(["ffprobe", "-v", "error", "-show_entries", "format=duration",
              "-of", "default=nw=1:nk=1", str(path)])
    return float(x.stdout.decode().strip())


def candidate_starts(base, length, extended=False, window=WINDOW):
    if base >= 100:
        starts = [base + shift for shift in (-30, -20, -10, -5, 0, 5, 10, 20, 30)]
    else:
        starts = [0, 2, 3.5, 4.5, 5, 5.5, 6.5, 7.5, 8, 8.5, 9.5, 10, 12, 16, 20, 24, 30, 40, base]
    if extended:
        starts.extend([45, 55, 65, 75, 85, 95, 105, 115, 125])
    return sorted({round(float(s), 2) for s in starts if 0 <= s <= length - window - 0.1})


def scan(path, start, window=WINDOW):
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "info",
           "-ss", str(start), "-i", str(path), "-t", str(window),
           "-an", "-vf", f"fps={FPS},scale=320:180,freezedetect=n=-40dB:d=1,format=gray",
           "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1"]
    p = call(cmd, timeout=65)
    frame_size = 320 * 180
    n = len(p.stdout) // frame_size
    if n < FPS * 3:
        raise RuntimeError(f"too few frames: {n}")
    frames = [memoryview(p.stdout)[i*frame_size:(i+1)*frame_size] for i in range(n)]
    diffs = [sum(abs(a-b) for a,b in zip(frames[i-1], frames[i])) / frame_size
             for i in range(1,n)]
    log = p.stderr.decode(errors="replace")
    freeze_starts = [float(x) for x in re.findall(r"freeze_start:\s*([0-9.]+)", log)]
    freeze_ends = [float(x) for x in re.findall(r"freeze_end:\s*([0-9.]+)", log)]
    intervals = []
    for i, st in enumerate(freeze_starts):
        end = freeze_ends[i] if i < len(freeze_ends) else window
        if end - st >= 0.95:
            intervals.append([round(st, 3), round(end, 3)])
    return {"start_seconds": start, "window_seconds": window,
            "frames": n, "mean_pixel_change": round(sum(diffs)/len(diffs), 4),
            "moving_frame_fraction": round(sum(d>1.0 for d in diffs)/len(diffs), 4),
            "freeze_intervals": intervals, "technical_candidate": not intervals}


def frame(path, t, dest):
    call(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(t),
          "-i", str(path), "-frames:v", "1", "-vf", "scale=480:-2",
          str(dest)], timeout=45)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/daily.json")
    ap.add_argument("--output", default="qa/source-motion-candidates")
    args = ap.parse_args()
    data = json.loads(Path(args.config).read_text(encoding="utf-8"))
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    cache = out / "cache"
    cache.mkdir(exist_ok=True)
    report = {"purpose": "source seek candidates only; NOT render/editorial/license approval",
              "targets": [], "config": args.config}
    for key, index in TARGETS:
        src = (data[key]["sources"][index] if index < len(data[key]["sources"])
               else ALTERNATES[(key, index)])
        ext = Path(urlsplit(src["url"]).path).suffix or ".webm"
        local = cache / f"{key}-{index:02d}{ext}"
        row = {"key": key, "source_index": index, "title": src.get("assetTitle"),
               "url": src["url"], "configured_seek": src.get("start_seconds", 0),
               "windows": [], "review_required": True}
        report["targets"].append(row)
        try:
            if not local.exists() or local.stat().st_size < 100_000:
                call(["curl", "-fL", "--retry", "3", "--retry-delay", "3",
                      "--connect-timeout", "25", "--max-time", "240",
                      "-A", "WildVox QA (nonpublishing source audit)",
                      "-o", str(local), src["url"]], timeout=270)
            length = duration(local)
            row["source_duration"] = round(length, 3)
            window = 3.0 if (key, index) == ("caribou_reindeer_one_species", 1) else WINDOW
            for st in candidate_starts(float(src.get("start_seconds", 0)), length,
                                       extended=(key == "red_fox_hunt_to_play" and index == 10),
                                       window=window):
                try:
                    row["windows"].append(scan(local, st, window=window))
                except Exception as e:
                    row.setdefault("window_errors", []).append(f"{st}: {e}")
            best = sorted(row["windows"], key=lambda x: (
                not x["technical_candidate"], -x["moving_frame_fraction"],
                -x["mean_pixel_change"]))[:3]
            row["top_motion_candidates"] = best
            for item in best:
                for offset in (1.0, 3.0):
                    name = f"{key}-{index:02d}-start{item['start_seconds']}-plus{offset}.jpg"
                    frame(local, item["start_seconds"] + offset, out / name)
                    item.setdefault("review_frames", []).append(name)
            print(f"{key}[{index}]: {len(row['windows'])} windows, "
                  f"{sum(x['technical_candidate'] for x in row['windows'])} freeze-free",
                  flush=True)
        except Exception as e:
            row["error"] = str(e)
            print(f"{key}[{index}]: ERROR {e}", flush=True)
        finally:
            (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Diagnostic finished: {len(report['targets'])} targets", flush=True)
    if any("error" in row or not row["windows"] for row in report["targets"]):
        raise SystemExit("Source motion scan incomplete; inspect report.json before changing seeks")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Experimental MoneyPrinterTurbo render of ONE approved WildVox candidate.

Runs only in an isolated GitHub Actions job (or locally). It:
  * reads (never writes) a candidate from a WildVox config;
  * downloads its Wikimedia Commons sources (same licensed footage);
  * generates the WildVox Kokoro pm_alex narration;
  * renders with the upstream MoneyPrinterTurbo CLI using local materials,
    the custom narration, Whisper subtitles and no music.

Cross-posting is forced off in config.toml and no publish credential exists in
the job. The output is a review artifact, never a post.
"""
import argparse
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

MIN_SHOTS, MAX_SHOTS = 6, 12

# WildVox look (brand from legal/*.html: Inter weight 900, white on #0b0d10,
# accent #ff4d22). Feedback 18/11/2026: no zoom/crop, video centred, captions
# below the video and above the TikTok UI area.
SUBTITLE_FONT = "Inter-Black.ttf"
SUBTITLE_STYLE = [
    "--video-fit-mode", "contain",          # full frame, no crop/zoom
    "--subtitle-position", "custom",
    "--custom-position", "82",              # inside the bottom bar, clear of 4-line captions on photos
    "--font-name", SUBTITLE_FONT,
    "--font-size", "52",                   # fewer lines -> stays in the bar
    "--text-fore-color", "#FFFFFF",         # WildVox white text ...
    "--no-subtitle-background-enabled",     # no box (feedback 18/11/2026)
    "--stroke-color", "#FF4D22",            # ... with WildVox orange outline
    "--stroke-width", "4",
]
LOGO_MARGIN_X, LOGO_Y = 48, 220             # top-right, inside the top black bar


def is_widescreen(width: int, height: int) -> bool:
    """Only ~16:9 shots leave a bottom bar for captions under `contain`."""
    return height > 0 and width / height >= 1.6


LABEL_Y = 530                               # above the media (photos reach y~594)


def logo_overlay_command(video: Path, logo: Path, out: Path, label: Path | None = None) -> list:
    inputs = ["-i", str(video), "-i", str(logo)]
    graph = f"[0:v][1:v]overlay=W-w-{LOGO_MARGIN_X}:{LOGO_Y}"
    if label is not None:
        inputs += ["-i", str(label)]
        graph += f"[v1];[v1][2:v]overlay=(W-w)/2:{LABEL_Y}"
    return ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
            "-filter_complex", graph,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "copy", str(out)]


def make_label(font: Path, text: str, out: Path) -> Path:
    """Honest on-screen note, e.g. footage of related species (not the new one)."""
    if not text or len(text) > 60:
        raise ValueError("Label must be 1-60 characters")
    subprocess.run(["magick", "-background", "none", "-font", str(font), "-pointsize", "34",
                    "-fill", "#FFFFFFCC", f"label:{text}", str(out)], check=True)
    return out


def make_wordmark(font: Path, out: Path) -> Path:
    """WildVox wordmark as on legal/*.html: 'Wild' white + 'Vox' orange, Inter 900."""
    subprocess.run(["magick", "-background", "none", "-font", str(font), "-pointsize", "72",
                    "-fill", "#FFFFFF", "label:Wild", "-fill", "#FF4D22", "label:Vox",
                    "+append", str(out)], check=True)
    return out

# (pattern, replacement) – every pattern MUST match exactly once.
SAFE_CONFIG = [
    (r'^video_source\s*=.*$', 'video_source = "local"'),
    (r'^subtitle_provider\s*=.*$', 'subtitle_provider = "whisper"'),
    (r'^upload_post_enabled\s*=.*$', 'upload_post_enabled = false'),
    (r'^upload_post_api_key\s*=.*$', 'upload_post_api_key = ""'),
    (r'^upload_post_username\s*=.*$', 'upload_post_username = ""'),
    (r'^upload_post_auto_upload\s*=.*$', 'upload_post_auto_upload = false'),
    (r'^model_size\s*=.*$', 'model_size = "small"'),
]


def write_safe_config(mpt_root: Path) -> Path:
    text = (mpt_root / "config.example.toml").read_text(encoding="utf-8")
    for pattern, repl in SAFE_CONFIG:
        text, n = re.subn(pattern, repl, text, flags=re.M)
        if n != 1:
            raise RuntimeError(f"Upstream config layout changed: {pattern!r} matched {n}x")
    out = mpt_root / "config.toml"
    out.write_text(text, encoding="utf-8")
    return out


def _is_commons(url: str, prefix: str) -> bool:
    p = urlsplit(url or "")
    return p.scheme == "https" and p.hostname == "commons.wikimedia.org" and p.path.startswith(prefix)


def is_pixabay(s: dict) -> bool:
    page, url = urlsplit(s.get("sourcePage") or ""), urlsplit(s.get("url") or "")
    return (page.scheme == "https" and page.hostname == "pixabay.com" and url.scheme == "https"
            and url.hostname == "cdn.pixabay.com" and s.get("license") == PIXABAY_LICENSE)


PIXABAY_LICENSE = "Pixabay Content License"
MIN_PHOTOS = 3
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def is_inat_photo(s: dict) -> bool:
    page, url = urlsplit(s.get("sourcePage") or ""), urlsplit(s.get("url") or "")
    return (page.scheme == "https" and page.hostname == "www.inaturalist.org"
            and page.path.startswith("/photos/") and url.scheme == "https"
            and url.hostname in {"inaturalist-open-data.s3.amazonaws.com", "static.inaturalist.org"}
            and bool(s.get("license")))


def is_landscape_photo(width: int, height: int) -> bool:
    """Photos may be a bit taller than 16:9 but must leave the caption bar free."""
    return height > 0 and width / height >= 1.45  # 1.25 let 4-line captions touch the photo


def validate_candidate(cand: dict) -> list:
    if not isinstance(cand, dict) or not (cand.get("script") or "").strip():
        raise ValueError("Candidate needs an approved script")
    if not cand.get("curiosity_fact_sheet"):
        raise ValueError("Candidate needs curiosity_fact_sheet (editorial policy 11/11/2026)")
    videos = [s for s in cand.get("sources") or [] if s.get("type", "video") in ("video", "image")]
    for s in videos:
        commons = _is_commons(s.get("sourcePage"), "/wiki/File:") and _is_commons(s.get("url"), "/wiki/Special:FilePath/")
        if not (commons or is_pixabay(s) or (s.get("type") == "image" and is_inat_photo(s))):
            raise ValueError("Only Wikimedia Commons, Pixabay or iNaturalist sources are allowed")
        if not (s.get("license") or "").strip():
            raise ValueError("Missing license metadata")
    if len({s["url"] for s in videos}) != len(videos):
        raise ValueError("Duplicate sources")
    photos_only = bool(videos) and all(s.get("type") == "image" for s in videos)
    low = MIN_PHOTOS if photos_only else MIN_SHOTS
    if not low <= len(videos) <= MAX_SHOTS:
        raise ValueError(f"Need {low}-{MAX_SHOTS} distinct sources")
    return videos


def clip_seconds(audio_seconds: float, n_shots: int) -> int:
    """Spread the real shots over the narration so footage is not looped."""
    return max(3, min(15, int(-(-audio_seconds // n_shots))))


def build_render_command(mpt_root: Path, script: str, shots: list, voice: Path,
                         python: str = sys.executable, clip: int = 5) -> list:
    if len(set(shots)) != len(shots):
        raise ValueError("Duplicate media are forbidden")
    photos_only = bool(shots) and all(Path(x).suffix.lower() in PHOTO_EXT for x in shots)
    if not (MIN_PHOTOS if photos_only else MIN_SHOTS) <= len(shots) <= MAX_SHOTS:
        raise ValueError(f"Need {MIN_SHOTS}-{MAX_SHOTS} shots ({MIN_PHOTOS} if photos)")
    return [
        python, str(mpt_root / "cli.py"),
        "--video-script", script,
        "--video-language", "pt-BR",
        "--video-source", "local",
        "--video-materials", ",".join(str(s) for s in shots),
        "--video-aspect", "9:16",
        "--video-concat-mode", "sequential",
        "--video-clip-duration", str(clip),
        "--image-motion", "static",           # owner prefers no zoom
        "--custom-audio-file", str(voice),
        "--bgm-type", "none",
        "--subtitle-enabled",
        *SUBTITLE_STYLE,
        "--stop-at", "video",
    ]


def prepare_media(videos: list, work: Path, used_out: list | None = None) -> list:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from generate_video import safe_download  # reuse WildVox downloader (read-only)
    work.mkdir(parents=True, exist_ok=True)
    shots = []
    for i, s in enumerate(videos):
        raw = work / f"raw_{i:02d}{Path(urlsplit(s['url']).path).suffix or '.mp4'}"
        if not safe_download(s["url"], raw):
            continue
        w, h = (int(x) for x in subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height", "-of", "csv=p=0", str(raw)],
            capture_output=True, text=True, check=True).stdout.strip().split(",")[:2])
        if s.get("type") == "image":
            if not is_landscape_photo(w, h) or w < 1200:
                print(f"Skipping photo {w}x{h}: {s['sourcePage']}", flush=True)
                continue
            jpg = work / f"shot_{i:02d}.jpg"
            subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw),
                            "-vf", "scale='min(1920,iw)':-2", "-q:v", "2", str(jpg)], check=True)
            shots.append(jpg.resolve())
            if used_out is not None:
                used_out.append(s)
            continue
        if not is_widescreen(w, h):
            print(f"Skipping non-widescreen shot {w}x{h}: {s['sourcePage']}", flush=True)
            continue
        mp4 = work / f"shot_{i:02d}.mp4"
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw),
                        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-pix_fmt", "yuv420p", str(mp4)], check=True)
        shots.append(mp4.resolve())
        if used_out is not None:
            used_out.append(s)
    return shots


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, default=Path("configs/daily.json"))
    ap.add_argument("--key", required=True)
    ap.add_argument("--mpt-root", type=Path, required=True)
    ap.add_argument("--work", type=Path, default=Path("work/mpt"))
    ap.add_argument("--mpt-python", default=sys.executable, help="Python of the isolated MPT venv")
    o = ap.parse_args(argv)

    cand = json.loads(o.config.read_text(encoding="utf-8"))[o.key]
    videos = validate_candidate(cand)
    write_safe_config(o.mpt_root)

    used_sources = []
    shots = prepare_media(videos, o.work, used_sources)
    need = MIN_PHOTOS if all(x.suffix == ".jpg" for x in shots) and shots else MIN_SHOTS
    if len(shots) < need:
        raise RuntimeError(f"Only {len(shots)} usable shots; need {need}")
    (o.work / "used_sources.json").write_text(json.dumps(used_sources, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from generate_video import generate_voice
    generate_voice(cand["script"], o.key, cand.get("visual_plan"),
                   cand.get("language", "pt-BR"), cand.get("voice"))
    voice = next(Path("output").glob(f"{o.key}_*.wav")).resolve()

    task_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"wildvox-mpt/{o.key}"))
    audio_s = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                    "-of", "csv=p=0", str(voice)], capture_output=True, text=True,
                                   check=True).stdout.strip())
    cmd = build_render_command(o.mpt_root, cand["script"], shots, voice, o.mpt_python,
                               clip_seconds(audio_s, len(shots)))
    cmd[-2:-2] = ["--task-id", task_id]
    print(json.dumps({"key": o.key, "shots": len(shots), "publish": False}, ensure_ascii=False), flush=True)
    subprocess.run(cmd, cwd=o.mpt_root, check=True, timeout=2400)

    task = o.mpt_root / "storage" / "tasks" / task_id
    logo = make_wordmark(o.mpt_root / "resource" / "fonts" / SUBTITLE_FONT, o.work / "wildvox-logo.png")
    label = None
    if cand.get("illustrative_label"):
        label = make_label(o.mpt_root / "resource" / "fonts" / SUBTITLE_FONT,
                           cand["illustrative_label"], o.work / "label.png")
    subprocess.run(logo_overlay_command(task / "final-1.mp4", logo, task / "final-1-wildvox.mp4", label), check=True)


if __name__ == "__main__":
    main()

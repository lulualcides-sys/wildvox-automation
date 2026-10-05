#!/usr/bin/env python3
import argparse
import hashlib
import json
import math
import re
import subprocess
from urllib.parse import urlsplit, urlunsplit
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
WORK = ROOT / "work"
OUT.mkdir(exist_ok=True)
WORK.mkdir(exist_ok=True)

def run(cmd):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run(cmd, check=True)

def probe_duration(path):
    r = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1",str(path)],
        capture_output=True,text=True,check=True
    )
    return float(r.stdout.strip())

def safe_download(url, path):
    if path.exists() and path.stat().st_size > 100_000:
        return
    run([
        "curl","-L","--fail","--retry","5","--retry-delay","2",
        "--connect-timeout","30","-A","Mozilla/5.0","-o",str(path),url
    ])

def generate_voice(text, key):
    print(f"Generating Kokoro am_michael narration for {key}...", flush=True)
    pipeline = KPipeline(lang_code="a")
    generator = pipeline(text, voice="am_michael", speed=1.08, split_pattern=r"\n+")
    chunks = []
    for item in generator:
        audio = getattr(item, "audio", None)
        if audio is None:
            audio = item[2]
        if hasattr(audio, "detach"):
            audio = audio.detach().cpu().numpy()
        audio = np.asarray(audio, dtype=np.float32).reshape(-1)
        if len(audio):
            chunks.append(audio)
    if not chunks:
        raise RuntimeError("Kokoro returned no audio")
    full = np.concatenate(chunks)
    wav = OUT / f"{key}_michael.wav"
    sf.write(wav, full, 24000)
    run([
        "ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(wav),
        "-codec:a","libmp3lame","-b:a","192k",str(OUT/f"{key}_michael.mp3")
    ])
    return wav, len(full) / 24000.0

def ass_escape(s):
    return s.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")

def ass_time(seconds):
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def weight(word):
    clean = re.sub(r"[^A-Za-z]","",word).lower()
    vowels = re.findall(r"[aeiouy]+",clean)
    return max(0.75, len(vowels)*1.05 + len(clean)*0.055)

def make_ass(text, title, key, duration):
    words = text.split()
    weights = [weight(w) for w in words]
    total = sum(weights)
    usable = max(0.1, duration - 0.10)
    starts = []
    t = 0.05
    for w in weights:
        starts.append(t)
        t += usable * (w / total)
    ends = starts[1:] + [duration]

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Caption,DejaVu Sans,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,150,150,390,1
Style: Hook,DejaVu Sans,76,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,6,2,8,90,90,215,1
Style: Brand,DejaVu Sans,34,&H00FFFFFF,&H00FFFFFF,&H00000000,&H70000000,-1,0,0,0,100,100,2,0,1,3,1,7,45,45,50,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    title_words = title.split()
    if len(title_words) > 4:
        mid = max(2, len(title_words)//2)
        hook = " ".join(title_words[:mid]) + r"\N" + " ".join(title_words[mid:])
    else:
        hook = title

    events = [
        f"Dialogue: 2,{ass_time(0)},{ass_time(min(2.05,duration))},Hook,,0,0,0,,{{\\an8}}{ass_escape(hook)}",
        f"Dialogue: 3,{ass_time(0)},{ass_time(duration)},Brand,,0,0,0,,{{\\an7}}WILD{{\\c&H616FFF&}}VOX"
    ]

    group_size = 4
    for i, (st, en) in enumerate(zip(starts, ends)):
        gs = (i // group_size) * group_size
        ge = min(len(words), gs + group_size)
        pieces = []
        for j in range(gs, ge):
            word = ass_escape(words[j].upper())
            if j == i:
                pieces.append(r"{\c&H616FFF&}" + word + r"{\c&HFFFFFF&}")
            else:
                pieces.append(word)
        events.append(
            f"Dialogue: 1,{ass_time(st)},{ass_time(en)},Caption,,0,0,0,,{' '.join(pieces)}"
        )

    ass = OUT / f"{key}_captions.ass"
    ass.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return ass

def canonical_url(url):
    parts = urlsplit(url)
    # Ignore query strings when deduplicating media URLs. This catches the same
    # Pexels/Wikimedia asset with different download parameters.
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))

def file_sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def interleave_video_first(videos, images):
    """Keep motion dominant without grouping all still images together."""
    if not images:
        return list(videos)
    if not videos:
        return list(images)

    ordered = []
    vi = ii = 0
    # Prefer roughly three video assets for every still whenever possible.
    while vi < len(videos) or ii < len(images):
        for _ in range(3):
            if vi < len(videos):
                ordered.append(videos[vi])
                vi += 1
        if ii < len(images):
            ordered.append(images[ii])
            ii += 1
        if vi >= len(videos):
            while ii < len(images):
                ordered.append(images[ii])
                ii += 1
    return ordered

def build_visual(sources, key, duration, min_unique_videos=4, max_shot_seconds=None, max_freeze_seconds=None):
    # URL-level dedupe before downloading.
    unique_sources = []
    seen_urls = set()
    for source in sources:
        if isinstance(source, str):
            source = {"url": source, "type": "video"}
        source = dict(source)
        url = source["url"]
        canon = canonical_url(url)
        if canon in seen_urls:
            print(f"Skipping duplicate source URL: {url}", flush=True)
            continue
        seen_urls.add(canon)
        unique_sources.append(source)

    # Download and byte-level dedupe. Different URLs sometimes point to the
    # exact same media, so hashing prevents identical clips/images from appearing.
    videos = []
    images = []
    seen_hashes = set()
    for idx, source in enumerate(unique_sources):
        media_type = source.get("type", "video")
        ext = ".jpg" if media_type == "image" else ".mp4"
        p = WORK / f"{key}_source_{idx}{ext}"
        safe_download(source["url"], p)
        digest = file_sha256(p)
        if digest in seen_hashes:
            print(f"Skipping duplicate media bytes: {source['url']}", flush=True)
            continue
        seen_hashes.add(digest)
        item = (p, media_type, source)
        if media_type == "video":
            videos.append(item)
        else:
            images.append(item)

    # Quality gate: WildVox is video-first. A species with too little motion
    # footage should be replaced during content planning instead of being padded
    # with a slideshow of stills.
    if len(videos) < min_unique_videos:
        raise RuntimeError(
            f"{key} has only {len(videos)} unique video source(s). "
            f"This render requires at least {min_unique_videos} distinct videos; "
            "choose another species or add more verified video footage instead of filling with images."
        )

    # Still images are supporting material only. Keep at least ~75% of the
    # selected assets as videos whenever video footage exists.
    max_images = max(1, len(videos) // 3)
    if len(images) > max_images:
        print(
            f"Video-first rule: using {max_images} of {len(images)} unique image(s).",
            flush=True,
        )
        images = images[:max_images]

    local = interleave_video_first(videos, images)
    if not local:
        raise RuntimeError("No unique media sources available")

    if max_shot_seconds:
        required_assets = math.ceil(duration / max_shot_seconds)
        if len(local) < required_assets:
            raise RuntimeError(
                f"{key} would need shots longer than {max_shot_seconds:.1f}s "
                f"({len(local)} unique assets for {duration:.1f}s). "
                f"Add at least {required_assets} unique assets to avoid repetitive pacing."
            )

    print(
        f"Unique media selected for {key}: {len(videos)} video(s), {len(images)} image(s). "
        "Each asset will be used at most once. Synthetic zoom is disabled.",
        flush=True,
    )

    # Never cycle back to a source. One source = one shot. The shot duration is
    # spread across the available unique assets, so the same clip/image is not
    # repeated to fill the narration.
    nshots = len(local)
    base_shot_len = duration / nshots
    shots = []

    for i, (src, media_type, _source_meta) in enumerate(local):
        remaining = max(0.05, duration - (i * base_shot_len))
        shot_len = remaining if i == nshots - 1 else base_shot_len
        out = WORK / f"{key}_shot_{i:02d}.mp4"

        # No zoompan, no animated scaling and no crop on the foreground.
        # Media is fitted once to the 9:16 canvas and padded.
        vf = (
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30"
        )

        if media_type == "image":
            run([
                "ffmpeg","-y","-hide_banner","-loglevel","error",
                "-loop","1","-i",str(src),"-t",f"{shot_len:.3f}","-an",
                "-vf",vf,
                "-c:v","libx264","-preset","veryfast","-crf","20",
                "-pix_fmt","yuv420p",str(out)
            ])
        else:
            srcdur = max(0.1, probe_duration(src))
            # Use one continuous, non-looping section from this clip.
            playable = min(shot_len, srcdur)
            maxstart = max(0.0, srcdur - playable)
            # Deterministic offset gives variety without reusing the same clip.
            start = 0.0 if maxstart <= 0 else ((i + 1) * 1.73) % maxstart
            run([
                "ffmpeg","-y","-hide_banner","-loglevel","error",
                "-ss",f"{start:.3f}","-i",str(src),
                "-t",f"{playable:.3f}","-an",
                "-vf",vf,
                "-c:v","libx264","-preset","veryfast","-crf","20",
                "-pix_fmt","yuv420p",str(out)
            ])

            # If a source clip is shorter than its assigned slot, freeze its last
            # frame rather than looping/repeating the video.
            if playable + 0.05 < shot_len:
                freeze_for = shot_len - playable
                if max_freeze_seconds is not None and freeze_for > max_freeze_seconds:
                    raise RuntimeError(
                        f"{key} source {i} is too short and would freeze for {freeze_for:.2f}s. "
                        f"Maximum allowed freeze is {max_freeze_seconds:.2f}s."
                    )
                padded = WORK / f"{key}_shot_{i:02d}_padded.mp4"
                run([
                    "ffmpeg","-y","-hide_banner","-loglevel","error",
                    "-i",str(out),
                    "-vf",f"tpad=stop_mode=clone:stop_duration={freeze_for:.3f}",
                    "-t",f"{shot_len:.3f}",
                    "-c:v","libx264","-preset","veryfast","-crf","20",
                    "-pix_fmt","yuv420p",str(padded)
                ])
                padded.replace(out)

        shots.append(out)

    concat = WORK / f"{key}_concat.txt"
    concat.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in shots) + "\n",
        encoding="utf-8"
    )
    visual = WORK / f"{key}_visual.mp4"
    run([
        "ffmpeg","-y","-hide_banner","-loglevel","error",
        "-f","concat","-safe","0","-i",str(concat),
        "-t",f"{duration:.3f}","-c","copy",str(visual)
    ])
    return visual

def render_final(visual, voice, ass, key, duration):
    final = OUT / f"{key}.mp4"
    run([
        "ffmpeg","-y","-hide_banner","-loglevel","error",
        "-i",str(visual),"-i",str(voice),"-vf",f"ass={ass.as_posix()}",
        "-map","0:v:0","-map","1:a:0","-t",f"{duration:.3f}",
        "-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","192k","-movflags","+faststart",str(final)
    ])
    return final

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("--config", default="configs/test_batch.json")
    args = ap.parse_args()

    data = json.loads((ROOT / args.config).read_text(encoding="utf-8"))
    cfg = data[args.key]

    voice, duration = generate_voice(cfg["script"], args.key)
    ass = make_ass(cfg["script"], cfg["title"], args.key, duration)
    visual = build_visual(
        cfg["sources"],
        args.key,
        duration,
        min_unique_videos=int(cfg.get("min_unique_videos", 4)),
        max_shot_seconds=float(cfg["max_shot_seconds"]) if cfg.get("max_shot_seconds") else None,
        max_freeze_seconds=float(cfg["max_freeze_seconds"]) if cfg.get("max_freeze_seconds") is not None else None,
    )
    final = render_final(visual, voice, ass, args.key, duration)

    (OUT / f"{args.key}_meta.json").write_text(
        json.dumps({
            "key": args.key,
            "title": cfg["title"],
            "caption": cfg["caption"],
            "duration": round(duration, 2),
            "voice": "am_michael",
            "speed": 1.08,
            "sources": cfg["sources"]
        }, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"FINAL={final}", flush=True)
    print(f"DURATION={duration:.2f}", flush=True)

if __name__ == "__main__":
    main()

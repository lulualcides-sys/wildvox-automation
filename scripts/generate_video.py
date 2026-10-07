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
        return True
    try:
        run([
            "curl","-L","--fail","--retry","5","--retry-delay","2",
            "--connect-timeout","30","-A","Mozilla/5.0","-o",str(path),url
        ])
    except subprocess.CalledProcessError:
        path.unlink(missing_ok=True)
        print(f"Skipping source that failed to download: {url}", flush=True)
        return False
    if not path.exists() or path.stat().st_size <= 100_000:
        path.unlink(missing_ok=True)
        print(f"Skipping source with invalid/empty download: {url}", flush=True)
        return False
    return True

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

def validate_daily_batch(data):
    """Enforce the non-negotiable editorial and media gates for daily.json."""
    if len(data) != 10:
        raise RuntimeError(f"daily.json must contain exactly 10 entries, found {len(data)}")

    short_count = 0
    long_count = 0
    batch_urls = set()

    for key, cfg in data.items():
        min_duration = float(cfg.get("min_duration", 0) or 0)
        max_duration = float(cfg.get("max_duration", 0) or 0)

        if (min_duration, max_duration) == (30.0, 45.0):
            short_count += 1
            required_videos = 6
        elif (min_duration, max_duration) == (60.0, 75.0):
            long_count += 1
            required_videos = 8
        else:
            raise RuntimeError(
                f"{key} must use duration gates 30-45s or 60-75s, "
                f"found {min_duration:.0f}-{max_duration:.0f}s"
            )

        trend_exception = cfg.get("trend_exception") or {}
        allow_photo_only = bool(trend_exception.get("photo_only_allowed"))

        sources = cfg.get("sources") or []
        if allow_photo_only:
            if not trend_exception.get("evidence_url") or not trend_exception.get("evidence_published_date"):
                raise RuntimeError(
                    f"{key} photo-only trend exception requires evidence_url and evidence_published_date"
                )
            if not 3 <= len(sources) <= 12:
                raise RuntimeError(
                    f"{key} photo-only trend exception must provide 3-12 unique authentic visual assets"
                )
        elif not 8 <= len(sources) <= 12:
            raise RuntimeError(f"{key} must provide a pool of 8-12 unique assets")

        video_count = 0
        image_count = 0
        for source in sources:
            if isinstance(source, str):
                source = {"url": source, "type": "video"}
            media_type = source.get("type", "video")
            if media_type == "video":
                video_count += 1
            elif media_type == "image":
                image_count += 1
            else:
                raise RuntimeError(f"{key} has unsupported media type: {media_type}")

            canon = canonical_url(source["url"])
            if canon in batch_urls:
                raise RuntimeError(f"Duplicate media URL across daily batch: {source['url']}")
            batch_urls.add(canon)

        if allow_photo_only:
            # Breaking/rediscovery exception: authentic scarcity is preferable to
            # substituting footage from another species. If genuine video exists,
            # it may still be mixed with the verified stills.
            if video_count == 0 and image_count < 3:
                raise RuntimeError(
                    f"{key} photo-only trend exception needs at least 3 unique authentic images"
                )
            if video_count > 10:
                raise RuntimeError(f"{key} may use at most 10 video clips in its source pool")
        else:
            if video_count < required_videos:
                raise RuntimeError(
                    f"{key} requires at least {required_videos} unique videos, found {video_count}"
                )
            if video_count > 10:
                raise RuntimeError(f"{key} may use at most 10 video clips in its source pool")
            if image_count > 2:
                raise RuntimeError(f"{key} may use at most 2 supporting still images")
            if int(cfg.get("min_unique_videos", 0) or 0) < required_videos:
                raise RuntimeError(
                    f"{key} min_unique_videos must be at least {required_videos}"
                )

        target = float(cfg.get("target_shot_seconds", 0) or 0)
        max_shot = float(cfg.get("max_shot_seconds", 0) or 0)
        max_freeze = float(cfg.get("max_freeze_seconds", 99))
        if allow_photo_only:
            if not 4.0 <= target <= 8.0:
                raise RuntimeError(
                    f"{key} photo-only target_shot_seconds must stay between 4 and 8"
                )
            if not 0 < max_shot <= 12.0:
                raise RuntimeError(
                    f"{key} photo-only max_shot_seconds must be at most 12"
                )
        else:
            if not 6.0 <= target <= 8.0:
                raise RuntimeError(f"{key} target_shot_seconds must stay between 6 and 8")
            if not 0 < max_shot <= 8.0:
                raise RuntimeError(f"{key} max_shot_seconds must be at most 8")
        if not 0 <= max_freeze <= 1.0:
            raise RuntimeError(f"{key} max_freeze_seconds must be at most 1")

    if short_count != 6 or long_count != 4:
        raise RuntimeError(
            f"daily.json must contain exactly 6 short and 4 long videos; "
            f"found {short_count} short and {long_count} long"
        )


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

def build_visual(sources, key, duration, min_unique_videos=4, max_shot_seconds=None, max_freeze_seconds=None, target_shot_seconds=None, visual_plan=None, allow_photo_only=False):
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
        if not safe_download(source["url"], p):
            continue

        source["_source_index"] = idx
        if media_type == "video":
            try:
                source_duration = probe_duration(p)
            except Exception as exc:
                print(f"Skipping invalid video source {source['url']}: {exc}", flush=True)
                p.unlink(missing_ok=True)
                continue
            if source_duration < 0.5:
                print(f"Skipping video source shorter than 0.5s: {source['url']}", flush=True)
                p.unlink(missing_ok=True)
                continue
            source["_duration"] = source_duration

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
    if not allow_photo_only and len(videos) < min_unique_videos:
        raise RuntimeError(
            f"{key} has only {len(videos)} unique video source(s). "
            f"This render requires at least {min_unique_videos} distinct videos; "
            "choose another species or add more verified video footage instead of filling with images."
        )

    if allow_photo_only and not videos and len(images) < 3:
        raise RuntimeError(
            f"{key} photo-only trend exception requires at least 3 unique authentic images"
        )

    # Still images are supporting material in normal videos. For verified
    # breaking/rediscovery stories, authentic photo-only storytelling is allowed
    # instead of substituting unrelated footage from another species.
    if not allow_photo_only:
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

    # Narrative-to-visual alignment gate. When content planning provides a
    # visual_plan, reserve one semantically tagged source for each narration
    # block before filling remaining shots. This makes the picture illustrate
    # what is being said instead of using unrelated generic footage.
    planned = []
    used_paths = set()
    if visual_plan:
        for block_index, block in enumerate(visual_plan):
            wanted = {
                str(tag).strip().lower()
                for tag in (block.get("tags") or [])
                if str(tag).strip()
            }
            if not wanted:
                continue

            match = None
            for item in local:
                src_path, _media_type, source_meta = item
                if str(src_path) in used_paths:
                    continue
                source_tags = {
                    str(tag).strip().lower()
                    for tag in (source_meta.get("tags") or [])
                    if str(tag).strip()
                }
                if wanted & source_tags:
                    match = item
                    break

            if match is None:
                description = block.get("scene") or block.get("text") or f"block {block_index + 1}"
                raise RuntimeError(
                    f"{key} visual plan has no tagged source for narration segment: {description}. "
                    f"Expected one of tags: {sorted(wanted)}"
                )

            planned.append(match)
            used_paths.add(str(match[0]))

        if planned:
            remaining = [item for item in local if str(item[0]) not in used_paths]
            local = planned + remaining

    # Use the source list as a pool, not a command to cram every clip into the edit.
    # Start near the requested 6-8 second cadence. If a selected source is too short
    # to support that cadence without a long freeze, automatically add another
    # unique source and shorten all shots slightly. This preserves the quality gate
    # without failing an otherwise usable batch because of one short stock clip.
    if target_shot_seconds:
        min_assets = 3 if allow_photo_only and not videos else min_unique_videos
        target_count = max(min_assets, round(duration / target_shot_seconds))
        target_count = min(len(local), max(min_assets, target_count))

        fixed = list(planned)
        fixed_paths = {str(item[0]) for item in fixed}
        candidates = [item for item in local if str(item[0]) not in fixed_paths]
        ranked_candidates = sorted(
            candidates,
            key=lambda item: (
                item[1] != "video",
                -float(item[2].get("_duration", 0.0)),
                int(item[2].get("_source_index", 0)),
            ),
        )
        selected = None

        for candidate_count in range(max(target_count, len(fixed)), len(local) + 1):
            candidate = fixed + ranked_candidates[:max(0, candidate_count - len(fixed))]

            shot_len = duration / candidate_count
            if max_shot_seconds and shot_len > max_shot_seconds:
                continue

            if max_freeze_seconds is not None:
                too_short = [
                    item for item in candidate
                    if item[1] == "video"
                    and float(item[2].get("_duration", 0.0)) + max_freeze_seconds + 0.05 < shot_len
                ]
                if too_short:
                    continue

            selected = candidate
            break

        if selected is None:
            durations = ", ".join(
                f"{float(item[2].get('_duration', 0.0)):.1f}s"
                for item in sorted(videos, key=lambda item: int(item[2].get("_source_index", 0)))
            )
            raise RuntimeError(
                f"{key} cannot meet the configured pacing/freeze gates with the downloaded clips. "
                f"Available video durations: [{durations}]. Add longer verified sources."
            )

        # Keep semantic narration order for planned shots. Supporting footage follows
        # in configured source order so the edit remains predictable.
        if fixed:
            support = sorted(
                [item for item in selected if str(item[0]) not in fixed_paths],
                key=lambda item: int(item[2].get("_source_index", 0)),
            )
            local = fixed + support
        else:
            local = sorted(selected, key=lambda item: int(item[2].get("_source_index", 0)))

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

    for i, (src, media_type, source_meta) in enumerate(local):
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
            srcdur = max(0.1, float(source_meta.get("_duration") or probe_duration(src)))
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

def prepare_music(cfg, key):
    """Download optional licensed background music for a render."""
    music = cfg.get("music")
    if not music:
        return None, None

    if isinstance(music, str):
        music = {"url": music}
    url = music.get("url")
    if not url:
        return None, None

    # Daily automation must keep provenance so we never mix unknown/protected music.
    if not music.get("license") or not music.get("source_page"):
        raise RuntimeError(
            f"{key} background music must include license and source_page metadata"
        )

    suffix = Path(urlsplit(url).path).suffix.lower()
    if suffix not in {".mp3", ".wav", ".m4a", ".aac", ".ogg"}:
        suffix = ".mp3"
    path = WORK / f"{key}_music{suffix}"
    if not safe_download(url, path):
        raise RuntimeError(f"{key} background music download failed")
    return path, music


def render_final(visual, voice, ass, key, duration, music_path=None, music_cfg=None):
    final = OUT / f"{key}.mp4"

    if not music_path:
        run([
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i",str(visual),"-i",str(voice),"-vf",f"ass={ass.as_posix()}",
            "-map","0:v:0","-map","1:a:0","-t",f"{duration:.3f}",
            "-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p",
            "-c:a","aac","-b:a","192k","-movflags","+faststart",str(final)
        ])
        return final

    music_cfg = music_cfg or {}
    gain_db = float(music_cfg.get("gain_db", -24.0))
    # Keep background music deliberately quiet. Never allow a config louder than -18 dB.
    gain_db = min(gain_db, -18.0)
    gain_db = max(gain_db, -36.0)

    # Voice remains the foreground. The music starts low and is ducked further
    # whenever narration is present, then both are peak-limited before encoding.
    filter_complex = (
        f"[2:a]volume={gain_db:.1f}dB[bg];"
        "[bg][1:a]sidechaincompress="
        "threshold=0.020:ratio=8:attack=20:release=300:makeup=1[ducked];"
        "[1:a][ducked]amix=inputs=2:duration=first:dropout_transition=0,"
        "alimiter=limit=0.95[aout]"
    )

    run([
        "ffmpeg","-y","-hide_banner","-loglevel","error",
        "-i",str(visual),
        "-i",str(voice),
        "-stream_loop","-1","-i",str(music_path),
        "-vf",f"ass={ass.as_posix()}",
        "-filter_complex",filter_complex,
        "-map","0:v:0","-map","[aout]","-t",f"{duration:.3f}",
        "-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","192k","-movflags","+faststart",str(final)
    ])
    return final

def make_review_sheet(final, key, duration):
    """Create a 12-frame contact sheet used by the automated visual QA stage."""
    sheet = OUT / f"{key}_review.jpg"
    sample_fps = max(0.05, 12.0 / max(duration, 1.0))
    run([
        "ffmpeg","-y","-hide_banner","-loglevel","error",
        "-i",str(final),
        "-vf",f"fps={sample_fps:.6f},scale=270:-2,tile=4x3:nb_frames=12:padding=4:margin=4",
        "-frames:v","1","-q:v","2",str(sheet)
    ])
    return sheet

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("--config", default="configs/test_batch.json")
    args = ap.parse_args()

    data = json.loads((ROOT / args.config).read_text(encoding="utf-8"))
    if Path(args.config).name == "daily.json":
        validate_daily_batch(data)
    cfg = data[args.key]

    voice, duration = generate_voice(cfg["script"], args.key)

    min_duration = float(cfg.get("min_duration", 0) or 0)
    max_duration = float(cfg.get("max_duration", 0) or 0)
    if min_duration and duration < min_duration:
        raise RuntimeError(
            f"{args.key} narration is too short: {duration:.2f}s. "
            f"Minimum required duration is {min_duration:.2f}s. "
            "Expand the script before publishing."
        )
    if max_duration and duration > max_duration:
        raise RuntimeError(
            f"{args.key} narration is too long: {duration:.2f}s. "
            f"Maximum allowed duration is {max_duration:.2f}s. "
            "Tighten the script before publishing."
        )

    ass = make_ass(cfg["script"], cfg["title"], args.key, duration)
    visual = build_visual(
        cfg["sources"],
        args.key,
        duration,
        min_unique_videos=int(cfg.get("min_unique_videos", 4)),
        max_shot_seconds=float(cfg["max_shot_seconds"]) if cfg.get("max_shot_seconds") else None,
        max_freeze_seconds=float(cfg["max_freeze_seconds"]) if cfg.get("max_freeze_seconds") is not None else None,
        target_shot_seconds=float(cfg["target_shot_seconds"]) if cfg.get("target_shot_seconds") else None,
        visual_plan=cfg.get("visual_plan"),
        allow_photo_only=bool((cfg.get("trend_exception") or {}).get("photo_only_allowed")),
    )
    music_path, music_cfg = prepare_music(cfg, args.key)
    final = render_final(
        visual, voice, ass, args.key, duration,
        music_path=music_path,
        music_cfg=music_cfg,
    )
    review_sheet = make_review_sheet(final, args.key, duration)

    (OUT / f"{args.key}_meta.json").write_text(
        json.dumps({
            "key": args.key,
            "title": cfg["title"],
            "caption": cfg["caption"],
            "duration": round(duration, 2),
            "voice": "am_michael",
            "speed": 1.08,
            "sources": cfg["sources"],
            "review_sheet": review_sheet.name,
            "music": music_cfg,
            "trend_exception": cfg.get("trend_exception")
        }, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"FINAL={final}", flush=True)
    print(f"DURATION={duration:.2f}", flush=True)

if __name__ == "__main__":
    main()

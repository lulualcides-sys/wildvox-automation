#!/usr/bin/env python3
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
WORK = ROOT / "work"
OUT.mkdir(exist_ok=True)
WORK.mkdir(exist_ok=True)

TEXT = """This animal has three hearts, blue blood, and one of the strangest nervous systems on Earth. An octopus has about two thirds of its neurons in its arms, so each arm can process information and react on its own. It can solve puzzles, open jars, remember solutions, use tools, and squeeze through tiny gaps because it has no bones. Its skin can change color and texture in seconds to hide from predators. And when danger gets too close, it can blast ink and jet away. The wildest part? One heart actually slows down when the octopus swims."""

PEXELS = [
    "https://videos.pexels.com/video-files/1312397/1312397-hd_1920_1080_30fps.mp4",
    "https://videos.pexels.com/video-files/15623347/15623347-uhd_3840_2160_25fps.mp4",
    "https://videos.pexels.com/video-files/17841948/17841948-uhd_3840_2160_25fps.mp4",
    "https://videos.pexels.com/video-files/6430081/6430081-uhd_3840_2160_25fps.mp4",
    "https://videos.pexels.com/video-files/5413821/5413821-hd_1920_1080_30fps.mp4",
]

STARTS = [0.0, 2.0, 1.0, 4.0, 6.0, 8.0, 10.0, 14.0, 6.0, 18.0, 14.0, 5.0, 20.0, 2.0, 11.0, 7.0]


def run(cmd):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run(cmd, check=True)


def safe_download(url, path):
    if path.exists() and path.stat().st_size > 100_000:
        return
    run([
        "curl", "-L", "--fail", "--retry", "4", "--retry-delay", "2",
        "--connect-timeout", "30", "-o", str(path), url,
    ])


def generate_voice():
    print("Generating Kokoro am_michael narration...", flush=True)
    pipeline = KPipeline(lang_code="a")
    generator = pipeline(
        TEXT,
        voice="am_michael",
        speed=1.08,
        split_pattern=r"\n+",
    )

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
    wav = OUT / "wildvox_michael.wav"
    sf.write(wav, full, 24000)
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(wav), "-codec:a", "libmp3lame", "-b:a", "192k",
        str(OUT / "wildvox_michael.mp3"),
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
    clean = re.sub(r"[^A-Za-z]", "", word).lower()
    vowels = re.findall(r"[aeiouy]+", clean)
    return max(0.75, len(vowels) * 1.05 + len(clean) * 0.055)


def make_ass(duration):
    words = TEXT.split()
    weights = [weight(w) for w in words]
    total = sum(weights)

    start_margin = 0.05
    usable = max(0.1, duration - 0.10)
    starts = []
    t = start_margin
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
Style: Caption,DejaVu Sans,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,120,120,390,1
Style: Hook,DejaVu Sans,88,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,6,2,8,60,60,220,1
Style: Brand,DejaVu Sans,34,&H00FFFFFF,&H00FFFFFF,&H00000000,&H70000000,-1,0,0,0,100,100,2,0,1,3,1,7,45,45,50,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    events = []
    events.append(
        f"Dialogue: 2,{ass_time(0)},{ass_time(min(2.05,duration))},Hook,,0,0,0,,"
        r"{\an8}3 HEARTS. {\c&H616FFF&}BLUE BLOOD.{\c&HFFFFFF&}\NARMS THAT THINK?"
    )
    events.append(
        f"Dialogue: 3,{ass_time(0)},{ass_time(duration)},Brand,,0,0,0,,"
        r"{\an7}WILD{\c&H616FFF&}VOX"
    )

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
        line = " ".join(pieces)
        events.append(
            f"Dialogue: 1,{ass_time(st)},{ass_time(en)},Caption,,0,0,0,,{line}"
        )

    ass = OUT / "wildvox_captions.ass"
    ass.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return ass


def build_visual(duration):
    local_sources = []
    for idx, url in enumerate(PEXELS):
        p = WORK / f"source_{idx}.mp4"
        safe_download(url, p)
        local_sources.append(p)

    shot_len = 3.15
    nshots = math.ceil(duration / shot_len)
    shot_files = []

    for i in range(nshots):
        src = local_sources[i % len(local_sources)]
        start = STARTS[i % len(STARTS)]
        out = WORK / f"shot_{i:02d}.mp4"
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{start:.2f}", "-i", str(src),
            "-t", f"{shot_len:.2f}",
            "-an",
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,setsar=1,fps=30",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p",
            out,
        ])
        shot_files.append(out)

    concat = WORK / "concat.txt"
    concat.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in shot_files) + "\n",
        encoding="utf-8",
    )

    visual = WORK / "visual.mp4"
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(concat),
        "-t", f"{duration:.3f}",
        "-c", "copy", str(visual),
    ])
    return visual


def render_final(visual, voice, ass, duration):
    final = OUT / "wildvox_octopus_michael_test.mp4"
    ass_filter = f"ass={ass.as_posix()}"
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(visual), "-i", str(voice),
        "-vf", ass_filter,
        "-map", "0:v:0", "-map", "1:a:0",
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(final),
    ])
    return final


def main():
    voice, duration = generate_voice()
    print(f"Narration duration: {duration:.2f}s", flush=True)
    ass = make_ass(duration)
    visual = build_visual(duration)
    final = render_final(visual, voice, ass, duration)
    print(f"FINAL={final}", flush=True)
    print(f"DURATION={duration:.2f}", flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Opt-in MoneyPrinterTurbo local-materials pilot; NEVER render/publish.

Uses only reviewed local WildVox sources and existing narration. Upstream
`--stop-at materials` stops BEFORE the video/cross-posting stage.
This script must not be called by scheduled WildVox production workflows.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv", ".ogv"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac"}


def safe_file(assets_root: Path, relative_name: str, extensions: set[str]) -> Path:
    if not isinstance(relative_name, str) or not relative_name or "," in relative_name:
        raise ValueError("Invalid local media path")
    path = (assets_root / relative_name).resolve()
    if not path.is_relative_to(assets_root) or not path.is_file():
        raise ValueError("Media must exist inside the explicit assets root")
    if path.suffix.lower() not in extensions:
        raise ValueError("Unsupported media extension")
    return path


def build_command(plan: dict, assets_root: Path, mpt_root: Path) -> list[str]:
    assets_root = assets_root.resolve(strict=True)
    mpt_root = mpt_root.resolve(strict=True)
    cli = mpt_root / "cli.py"
    if not cli.is_file():
        raise ValueError("Upstream MoneyPrinterTurbo cli.py not found")
    if not isinstance(plan, dict):
        raise ValueError("Plan must be a JSON object")
    script = plan.get("script")
    if not isinstance(script, str) or not script.strip() or len(script) > 4000:
        raise ValueError("A reviewed English narration script is required")
    items = plan.get("sources")
    if not isinstance(items, list) or not 8 <= len(items) <= 12:
        raise ValueError("Exactly 8-12 approved distinct local shots required")
    media = []
    for item in items:
        if not isinstance(item, dict) or item.get("reviewed") is not True:
            raise ValueError("Each shot requires explicit visual review")
        if not isinstance(item.get("license"), str) or not item["license"].strip():
            raise ValueError("Missing attribution/license metadata")
        source = urlsplit(str(item.get("source_page") or ""))
        if source.scheme != "https" or source.hostname != "commons.wikimedia.org" or not source.path.startswith("/wiki/File:"):
            raise ValueError("Source must point to a Wikimedia Commons file page")
        media.append(safe_file(assets_root, item.get("file"), VIDEO_EXTENSIONS))
    if len(set(media)) != len(media):
        raise ValueError("Duplicate media are forbidden")
    if not isinstance(plan.get("narration_file"), str):
        raise ValueError("Original WildVox voiceover required")
    voice = safe_file(assets_root, plan["narration_file"], AUDIO_EXTENSIONS)
    # Never allow network stock sources, AI TTS, paid media providers, automatic
    # subtitles, or the 'video' stage which may run cross-posting integrations.
    return [
        sys.executable, str(cli),
        "--video-script", script,
        "--video-source", "local",
        "--video-materials", ",".join(str(m) for m in media),
        "--video-aspect", "9:16",
        "--custom-audio-file", str(voice),
        "--no-subtitle-enabled",
        "--bgm-type", "none",
        "--stop-at", "materials",
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--assets-root", required=True, type=Path)
    parser.add_argument("--mpt-root", required=True, type=Path)
    parser.add_argument("--execute", action="store_true", help="Run ONLY offline materials preflight (never video)")
    opts = parser.parse_args(argv)
    plan = json.loads(opts.plan.read_text(encoding="utf-8"))
    cmd = build_command(plan, opts.assets_root, opts.mpt_root)
    print(json.dumps({"stage": "materials", "publish": False, "command": cmd}, ensure_ascii=False))
    if opts.execute:
        subprocess.run(cmd, cwd=opts.mpt_root, check=True, timeout=900)


if __name__ == "__main__":
    main()

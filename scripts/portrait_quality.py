"""Fail-closed guard against blurred 9:16 filler around unreviewed B-roll."""
import json
import subprocess

TARGET_RATIO = 9 / 16
MIN_FOREGROUND_FRACTION = 0.90


def effective_ratio(width, height, crop=None):
    """Aspect ratio after the renderer's optional static center crop."""
    if width <= 0 or height <= 0:
        raise ValueError("Video/image must have positive dimensions")
    if crop is None:
        return width / height
    if crop == "9:16":
        return TARGET_RATIO
    if crop == "4:5":
        return 4 / 5
    raise ValueError(f"Unsupported portrait_crop: {crop!r}")


def foreground_fraction(width, height, crop=None):
    """Fraction of the 9:16 output occupied by the authentic sharp shot."""
    ratio = effective_ratio(width, height, crop)
    return min(ratio / TARGET_RATIO, TARGET_RATIO / ratio)


def probe_dimensions(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    streams = json.loads(result.stdout).get("streams") or []
    if not streams:
        raise RuntimeError(f"No visual stream in {path}")
    return int(streams[0]["width"]), int(streams[0]["height"])


def require_reviewed_portrait(path, source_meta):
    """Reject unfilled portrait layouts; never auto-crop without subject review."""
    meta = source_meta or {}
    crop = meta.get("portrait_crop")
    width, height = probe_dimensions(path)
    fraction = foreground_fraction(width, height, crop)
    if fraction < MIN_FOREGROUND_FRACTION:
        raise RuntimeError(
            f"Unapproved blurred portrait filler: {path} ({width}x{height}, "
            f"portrait_crop={crop!r}, sharp foreground {fraction:.0%}). "
            "Use naturally vertical licensed footage or inspect the full "
            "source and set portrait_crop='9:16' only if the animal stays visible."
        )
    return fraction

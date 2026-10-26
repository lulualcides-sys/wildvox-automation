"""Narration-synced cinematic ASS overlays; stdlib + FFmpeg/libass only.

Arrows target manually reviewed normalized positions. Never pretend to detect
an animal, anatomical feature or prey automatically.
"""
import math
from pathlib import Path

STYLES = """Style: FxLabel,DejaVu Sans,46,&H00FFFFFF,&H00FFFFFF,&H00000000,&HA6000000,-1,0,0,0,100,100,0,0,3,15,0,7,75,75,75,1
Style: FxShape,DejaVu Sans,25,&H004AD0F2,&H004AD0F2,&H004AD0F2,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
"""
GOLD = "&H4AD0F2&"
ROLES = {"hook": "LOOK CLOSER", "payoff": "THE REVEAL"}
TYPES = {"arrow", "ring", "box", "label"}


def timestamp(seconds):
    seconds = max(0, seconds)
    return f"{int(seconds // 3600)}:{int(seconds // 60) % 60:02d}:{seconds % 60:05.2f}"


def point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("FX point must be [normalized_x, normalized_y]")
    x, y = value
    if any(not isinstance(q, (int, float)) or isinstance(q, bool)
           or not math.isfinite(q) for q in (x, y)):
        raise ValueError("FX coordinates must be finite numbers")
    if not (0.04 <= x <= .96 and .10 <= y <= .82):
        raise ValueError("FX coordinates are outside the safe video area")
    return round(x * 1080), round(y * 1920)


def arrow(start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 48:
        raise ValueError("FX arrow too short")
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    h = min(43, length * .36)
    bx, by = dx - ux * h, dy - uy * h
    shape = [(px * 5, py * 5), (bx + px * 5, by + py * 5),
             (bx + px * 20, by + py * 20), (dx, dy),
             (bx - px * 20, by - py * 20), (bx - px * 5, by - py * 5),
             (-px * 5, -py * 5)]
    return polygon(shape)


def polygon(points):
    return "m " + " l ".join(f"{round(x)} {round(y)}" for x, y in points) + " c"


def ring(radius):
    return polygon([(math.cos(i * 2 * math.pi / 48) * radius,
                     math.sin(i * 2 * math.pi / 48) * radius)
                    for i in range(48)])


def rectangle(width, height):
    w, h = width / 2, height / 2
    return polygon([(-w, -h), (w, -h), (w, h), (-w, h)])


def event(start, end, style, content):
    return f"Dialogue: 5,{timestamp(start)},{timestamp(end)},{style},,0,0,0,,{content}"


def label(text, x, y, start, end):
    cleaned = (str(text).replace("\\", "").replace("{", "(")
               .replace("}", ")").replace("\n", " ").strip()[:34].upper())
    if not cleaned:
        return None
    fx = (r"{\an7\move(" + f"{x},{y+24},{x},{y},0,260)"
          + r"\fscx90\fscy90\t(0,260,\fscx100\fscy100)\fad(160,240)}")
    return event(start, end, "FxLabel", fx + cleaned)


def shape(path, x, y, start, end, outline=False):
    tags = r"{\an7\pos(" + f"{x},{y}" + r")\p1\shad0"
    if outline:
        tags += (r"\1a&HFF&\3c" + GOLD
                 + r"\bord6\fscx80\fscy80"
                 + r"\t(0,230,\fscx108\fscy108)"
                 + r"\t(230,450,\fscx100\fscy100)")
    else:
        tags += (r"\1c" + GOLD + r"\bord0\fscx30\fscy30"
                 + r"\t(0,320,\fscx100\fscy100)")
    tags += r"\fad(130,230)}"
    return event(start, end, "FxShape", tags + path + r"{\p0}")


def build_events(timeline):
    if not any(block.get("story_role") for block in timeline):
        return []
    result = []
    for block in timeline:
        t0, end = float(block["start"]), float(block["end"])
        if end - t0 < .4:
            continue
        role = block.get("story_role")
        caption = block.get("overlay_label")
        if caption is None:
            caption = ROLES.get(role)
        if caption:
            line = label(caption, 82, 1150, t0 + .08, min(end, t0 + 1.95))
            if line:
                result.append(line)
        effects = block.get("fx") or []
        if not isinstance(effects, list) or len(effects) > 2:
            raise ValueError("A spoken block permits at most 2 reviewed overlays")
        for fx in effects:
            if not isinstance(fx, dict) or fx.get("type") not in TYPES:
                raise ValueError("Unknown overlay effect")
            delay = float(fx.get("delay", 0))
            length = float(fx.get("duration", 1.7))
            if not 0 <= delay <= 6 or not .35 <= length <= 3:
                raise ValueError("Overlay duration or delay is invalid")
            start = t0 + delay
            stop = min(end, start + length)
            if stop - start < .35:
                raise ValueError("Overlay exceeds speech block")
            kind = fx["type"]
            if kind == "arrow":
                a, b = point(fx.get("from")), point(fx.get("to"))
                result.append(shape(arrow(a, b), *a, start, stop))
            elif kind == "ring":
                x, y = point(fx.get("center"))
                radius = float(fx.get("radius", .06))
                if not .025 <= radius <= .18:
                    raise ValueError("Invalid ring radius")
                result.append(shape(ring(radius * 1080), x, y, start, stop, True))
            elif kind == "box":
                x, y = point(fx.get("center"))
                w, h = float(fx.get("width", .24)), float(fx.get("height", .12))
                if not (.04 <= w <= .65 and .03 <= h <= .38):
                    raise ValueError("Invalid highlight dimensions")
                result.append(shape(rectangle(w * 1080, h * 1920),
                                    x, y, start, stop, True))
            elif kind == "label":
                x, y = point(fx.get("position"))
                line = label(fx.get("text", ""), x, y, start, stop)
                if line:
                    result.append(line)
    return result


def enrich_subtitles(path, timeline):
    events = build_events(timeline)
    if not events:
        return False
    p = Path(path)
    original = p.read_text(encoding="utf-8")
    if "\n[Events]\n" not in original:
        raise ValueError("Invalid existing ASS caption track")
    p.write_text(original.replace("\n[Events]\n", "\n" + STYLES + "\n[Events]\n", 1)
                 .rstrip("\n") + "\n" + "\n".join(events) + "\n", encoding="utf-8")
    return True


def camera_filter(base_filter, duration, role):
    """Gentle 4.5% progressive documentary push, only for hook and payoff."""
    if role not in {"hook", "payoff"}:
        return base_filter
    frames = max(1, round(float(duration) * 30))
    return (base_filter +
            ",zoompan=z='min(1.045,1+0.045*on/" + str(frames) + ")'"
            ":x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2'"
            ":d=1:s=1080x1920:fps=30")

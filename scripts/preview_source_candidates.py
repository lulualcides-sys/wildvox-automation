#!/usr/bin/env python3
"""Create source-only visual contact sheets; never approve or publish."""
import argparse, hashlib, json, subprocess, time
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from PIL import Image, ImageDraw, ImageOps

def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True)

def resolve_media(name, maxbytes):
    """Use the licensed Commons original, or a real video transcode when oversized.

    Never download a multi-hundred-MB original just to learn it is too large.
    Wikimedia's imageinfo derivatives are authentic encodings of that same file.
    """
    api = "https://commons.wikimedia.org/w/api.php?" + urlencode({
        "action": "query", "format": "json", "formatversion": 2,
        "prop": "imageinfo", "iiprop": "url|size|mime|derivatives",
        "titles": "File:" + name,
    })
    request = Request(api, headers={"User-Agent": "WildVox-QA/1.0 (Wikimedia Commons editorial source preview)"})
    for attempt in range(4):
        try:
            with urlopen(request, timeout=35) as response:
                payload = json.load(response)
            break
        except HTTPError as exc:
            if exc.code != 429 or attempt == 3:
                raise
            time.sleep(8 * (attempt + 1))
    time.sleep(2.5)  # Courtesy throttle for Commons source preview API
    pages = payload.get("query", {}).get("pages", [])
    info = (pages[0].get("imageinfo") or [{}])[0] if pages else {}
    original = info.get("url")
    if not original:
        raise ValueError("Commons API did not return an original file URL")
    if int(info.get("size", maxbytes + 1)) <= maxbytes:
        return original, False
    # TimedMediaHandler exposes video encodings through videoinfo, not always
    # through imageinfo. Try both before declaring a large file unpreviewable.
    options = list(info.get("derivatives") or [])
    if not options:
        video_api = "https://commons.wikimedia.org/w/api.php?" + urlencode({
            "action": "query", "format": "json", "formatversion": 2,
            "prop": "videoinfo", "viprop": "derivatives",
            "titles": "File:" + name,
        })
        try:
            with urlopen(Request(video_api, headers={
                "User-Agent": "WildVox-QA/1.0 (Wikimedia Commons editorial source preview)"
            }), timeout=35) as response:
                video_payload = json.load(response)
            video_pages = video_payload.get("query", {}).get("pages", [])
            if video_pages:
                options = (video_pages[0].get("videoinfo") or [{}])[0].get("derivatives") or []
        except (OSError, ValueError):
            options = []
    derivatives = []
    for d in options:
        src = d.get("src", "")
        if src.startswith("//upload.wikimedia.org/"):
            src = "https:" + src
        width = int(d.get("width") or 0)
        height = int(d.get("height") or 0)
        if (src.startswith("https://upload.wikimedia.org/") and
                src.lower().split("?")[0].endswith((".webm", ".mp4", ".ogv")) and
                width >= 360 and height >= 200 and width <= 1280):
            derivatives.append((abs(width - 960), -width, src))
    if not derivatives:
        raise ValueError("Original exceeds preview cap; Commons imageinfo/videoinfo returned no usable video transcode")
    derivatives.sort()
    return derivatives[0][2], True

def preview(item, out, index, maxbytes):
    url = item["sourcePage"]
    p = urlsplit(url)
    if p.netloc != "commons.wikimedia.org" or "/wiki/File:" not in p.path:
        raise ValueError("Not a Wikimedia Commons file page")
    name = unquote(p.path.split("/wiki/File:",1)[1]).replace("_"," ")
    if not name or "/" in name or "\\" in name:
        raise ValueError("Invalid Commons file name")
    key = f"candidate_{index:02d}"
    # Discovery already recorded the verified Commons original URL, MIME and
    # byte size. Reuse that exact original to avoid redundant API calls/429s.
    # Reject arbitrary domains and filenames; oversized originals still require
    # an official Commons derivative lookup.
    cached = item.get("verified_original_url")
    size = int(item.get("verified_original_size") or 0)
    if cached and 100000 < size <= maxbytes:
        parsed = urlsplit(cached)
        remote_name = unquote(Path(parsed.path).name).replace("_", " ")
        if (parsed.scheme != "https" or parsed.netloc != "upload.wikimedia.org"
                or remote_name != name):
            raise ValueError("Verified original URL does not match Commons filename")
        direct, used_transcode = cached, False
    else:
        direct, used_transcode = resolve_media(name, maxbytes)
    ext = Path(urlsplit(direct).path).suffix.lower()
    if ext not in (".webm", ".mp4", ".ogv"):
        raise ValueError("Commons returned a non-video URL")
    media = out / (key + ext)
    run(["curl","-L","--fail","--retry","3","--retry-delay","2",
         "--connect-timeout","20","--max-time","240","--max-filesize",str(maxbytes),
         "-A","Mozilla/5.0 (WildVox editorial preview)","-o",str(media),direct])
    if not media.is_file() or media.stat().st_size < 100000:
        raise ValueError("Missing or invalid media")
    info = json.loads(run(["ffprobe","-v","error","-show_entries",
                           "format=duration:stream=codec_type,width,height",
                           "-of","json",str(media)]).stdout)
    duration = float(info["format"]["duration"])
    if duration < 2:
        raise ValueError("Video too short")
    sheet = Image.new("RGB",(1980,410),"white")
    draw = ImageDraw.Draw(sheet)
    sample_seconds = item.get("sample_seconds")
    if sample_seconds is None:
        times = [duration * frac for frac in (.12, .5, .85)]
    else:
        if not isinstance(sample_seconds, list) or len(sample_seconds) != 3:
            raise ValueError("sample_seconds must contain exactly three timestamps")
        times = [float(t) for t in sample_seconds]
        if any(t < 0 or t >= duration for t in times):
            raise ValueError("sample_seconds timestamps must be within video duration")
    for i,second in enumerate(times):
        frame = out / f"{key}_{i}.jpg"
        run(["ffmpeg","-y","-hide_banner","-loglevel","error","-ss",
             f"{second:.3f}","-i",str(media),"-frames:v","1",
             "-vf","scale=640:360:force_original_aspect_ratio=decrease",str(frame)])
        with Image.open(frame) as im:
            thumb = ImageOps.contain(im.convert("RGB"),(640,360))
            sheet.paste(thumb,(i*660+(660-thumb.width)//2,28+(360-thumb.height)//2))
        draw.text((i*660+10,6),f"{key} | {second:.1f}s",fill="black")
        frame.unlink(missing_ok=True)
    output = out / f"{key}_preview.jpg"
    sheet.save(output,quality=90)
    sha = hashlib.sha256(media.read_bytes()).hexdigest()
    result = {"title":name,"sourcePage":url,"for_key":item.get("for_key"),
              "target_block":item.get("target_block"),"license":item.get("license"),
              "license_url":item.get("license_url"),"duration":duration,
              "bytes":media.stat().st_size,"sha256":sha,"preview":output.name,
              "preview_media_url":direct,"used_transcode":used_transcode,
              "status":"AWAITING_VISUAL_REVIEW"}
    media.unlink(missing_ok=True)
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--candidates",required=True)
    ap.add_argument("--out",required=True)
    ap.add_argument("--max-megabytes",type=int,default=90)
    a=ap.parse_args()
    data=json.loads(Path(a.candidates).read_text(encoding="utf-8"))
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    records=[]
    for i,item in enumerate(data.get("candidates",[])):
        if item.get("status")!="CANDIDATE_UNREVIEWED":
            continue
        try:
            record=preview(item,out,i,a.max_megabytes*1024*1024)
        except (OSError,ValueError,subprocess.CalledProcessError) as exc:
            record={"title":item.get("title"),"sourcePage":item.get("sourcePage"),
                    "status":"PREVIEW_FAILED_OR_OVERSIZE","error":str(exc)[:400]}
        records.append(record)
    (out/"manifest.json").write_text(json.dumps({
        "day":data.get("day"),"source_config_sha":data.get("current_config_blob_sha"),
        "publication_hold":True,"editorial_approval":False,"candidates":records
    },indent=2),encoding="utf-8")
    print(json.dumps({"previewed":sum(x["status"]=="AWAITING_VISUAL_REVIEW" for x in records),
                      "failed":sum(x["status"]!="AWAITING_VISUAL_REVIEW" for x in records)}))
if __name__=="__main__":
    main()

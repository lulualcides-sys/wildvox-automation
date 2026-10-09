#!/usr/bin/env bash
# Smoke isolado de editor; nao altera nenhum video real.
set -euo pipefail
mkdir -p artifacts
CHECKSUM="35743d048fcd942a1fe36b8c95f0af7b3ce7d5577325afabfae1083175d22fa5"
URL="https://github.com/storytold/filmcraft/releases/download/v0.2.0/filmcraft-0.2.0-linux-x86_64.tar.gz"
export CHECKSUM URL
python - <<'PY'
import json,os
open("artifacts/filmcraft-evaluation.json","w").write(json.dumps({
"version":"v0.2.0","workflow":"isolated_smoke","status":"started",
"original_renderer":"FFmpeg (untouched)","full_vertical_export_tested":False
},indent=2)+"\n")
PY
# Baseline de video vertical com ffmpeg: usa midia sintética.
ffmpeg -hide_banner -loglevel error -y -f lavfi -i "color=c=blue:s=360x640:r=24:d=2" -c:v libx264 -pix_fmt yuv420p -t 2 artifacts/wildvox-synthetic-ffmpeg.mp4
ffprobe -v error -show_entries stream=codec_name,width,height,avg_frame_rate -show_entries format=duration -of json artifacts/wildvox-synthetic-ffmpeg.mp4 > artifacts/ffmpeg-baseline.json
curl -fLsS --retry 2 --max-time 100 "$URL" -o /tmp/filmcraft-release.tar.gz || {
  python - <<'PY'
import json
p="artifacts/filmcraft-evaluation.json";d=json.load(open(p));d.update(status="release_unavailable",note="Nao foi possivel baixar a release oficial; render atual preservado.");open(p,"w").write(json.dumps(d,indent=2)+"\n")
PY
  exit 0
}
echo "$CHECKSUM  /tmp/filmcraft-release.tar.gz" | sha256sum -c --status || exit 1
mkdir -p /tmp/filmcraft-eval
tar -xzf /tmp/filmcraft-release.tar.gz -C /tmp/filmcraft-eval
find /tmp/filmcraft-eval -maxdepth 3 -type f | head -40 > artifacts/release-file-list.txt
binary="$(find /tmp/filmcraft-eval -maxdepth 4 -type f -name 'filmcraft-cli' -print -quit)"
status="cli_missing_in_release"
if [ -n "$binary" ]; then
  chmod +x "$binary"
  if timeout 25s "$binary" commands > artifacts/filmcraft-commands.txt 2> artifacts/filmcraft-stderr.txt; then
    status="cli_commands_passed"
  else
    status="cli_commands_failed"
  fi
fi
STATUS="$status" python - <<'PY'
import json,os
p="artifacts/filmcraft-evaluation.json";d=json.load(open(p))
d.update(status=os.environ["STATUS"],release_checksum_verified=True,
         full_vertical_export_tested=False,
         note="Smoke validou distribuicao/CLI quando disponivel. Nenhum render WildVox foi substituido.")
open(p,"w").write(json.dumps(d,indent=2)+"\n")
print(json.dumps(d,indent=2))
PY

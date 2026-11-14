#!/usr/bin/env python3
"""Prepare a copy-ready Publer Free packet only for independent QA-approved videos."""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from publer_handoff import prepare

TZ = ZoneInfo("America/Sao_Paulo")


def check_direct_mp4(url):
    req = Request(url, method="HEAD", headers={"User-Agent": "WildVox-Manual-Publer"})
    with urlopen(req, timeout=25) as resp:
        mime = resp.headers.get("Content-Type", "").split(";")[0].lower()
        if resp.status != 200 or mime not in ("video/mp4", "application/octet-stream"):
            raise RuntimeError("Direct MP4 URL is not publicly accessible")


def build(config, media_dir, reviews, now, selected=None, check=check_direct_mp4):
    if not isinstance(config, dict) or len(config) > 5:
        raise RuntimeError("Too many entries or invalid daily config")
    if selected and selected not in config:
        raise RuntimeError("Unknown candidate key")
    approved, held = [], []
    for key in ([selected] if selected else config):
        item = config[key]
        if not str(item.get("revision", "")).startswith(now.date().isoformat()):
            held.append((key, "stale editorial revision"))
            continue
        try:
            packet = prepare(key, config, media_dir, reviews, now)
            check(packet["title"])
            approved.append(packet)
        except (RuntimeError, ValueError, OSError) as exc:
            held.append((key, str(exc)[:250]))
    return approved, held


def report(approved, held, now):
    parts = [
        "# WildVox: Publer gratuito - " + now.strftime("%d/%m/%Y"),
        "",
        "Destino exclusivo: TikTok @wildvox. Isto NAO confirma agendamento nem publicacao.",
        "",
    ]
    if not approved:
        parts.append("Nenhum video NOVO com aprovacao independente e hash exato disponivel.")
        parts.append("Nao publicar videos antigos ou reprovados.")
    for i, packet in enumerate(approved, 1):
        parts += [
            "",
            "## Video " + str(i) + ": " + packet["key"],
            "Link direto do MP4 (copiar no Publer Media > URL):",
            packet["title"],
            "",
            "Legenda completa com creditos (copiar integralmente):",
            packet["body"],
            "",
            "SHA256: " + packet["sha256"],
            "Proximo horario de hoje: " + packet["next_slot"],
        ]
    if held:
        parts += ["", "## Retidos, nao publicar"]
        parts.extend("- " + key + ": " + why for key, why in held)
    parts += ["", "No Publer: Create > TikTok @wildvox > URL do video > legenda > AutoSchedule.",
              "Slots: 10:05, 12:40, 16:10, 19:35, 22:05 Sao Paulo. "
              "Confira agendamentos e URLs publicas no proprio TikTok.", ""]
    return "\n".join(parts)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--key")
    p.add_argument("--config", default="configs/daily.json")
    p.add_argument("--media-dir", default="media-branch")
    p.add_argument("--reviews", default="qa/reviews")
    a = p.parse_args()
    now = datetime.now(TZ)
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    approved, held = build(cfg, Path(a.media_dir), Path(a.reviews), now, a.key)
    text = report(approved, held, now)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write(text + "\n")


if __name__ == "__main__":
    main()

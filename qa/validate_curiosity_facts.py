#!/usr/bin/env python3
"""Fail closed on missing curiosity evidence for newly prepared WildVox videos.

Checks an explicit factual-research contract; it does NOT independently prove
scientific truth or replace the original-video editorial review.
"""
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

EFFECTIVE = date(2026, 11, 11)
REQUIRED = (
    "hook_question", "verified_fact", "biological_explanation",
    "comparison_or_consequence", "visual_evidence_strategy", "fact_sources",
)
REJECTED_HOSTS = ("commons.wikimedia.org", "tiktok.com", "youtube.com", "youtu.be")


def applies(entry):
    match = re.match(r"^(\d{4}-\d{2}-\d{2})(?:-|$)", str(entry.get("revision") or ""))
    if not match:
        raise ValueError("Missing valid YYYY-MM-DD revision")
    return date.fromisoformat(match.group(1)) >= EFFECTIVE


def validate_entry(key, entry):
    if not applies(entry):
        return
    if entry.get("publication_hold") is not True:
        raise ValueError(f"{key}: publication_hold=true required")
    if entry.get("language") != "pt-BR" or entry.get("voice") != "pm_alex":
        raise ValueError(f"{key}: factual videos must use pt-BR/pm_alex")
    sheet = entry.get("curiosity_fact_sheet")
    if not isinstance(sheet, dict):
        raise ValueError(f"{key}: missing curiosity_fact_sheet; B-roll description is not an educational script")
    for field in REQUIRED[:-1]:
        val = sheet.get(field)
        if not isinstance(val, str) or len(val.strip()) < 16:
            raise ValueError(f"{key}: missing substantive {field}")
    statements = [sheet[name].strip().casefold() for name in
                  ("verified_fact", "biological_explanation", "comparison_or_consequence")]
    if len(set(statements)) != 3:
        raise ValueError(f"{key}: fact, mechanism and comparison must be distinct")
    sources = sheet.get("fact_sources")
    if not isinstance(sources, list) or len(sources) < 2:
        raise ValueError(f"{key}: factual claims require independent fact_sources")
    for i, source in enumerate(sources, 1):
        if not isinstance(source, dict):
            raise ValueError(f"{key}: invalid fact_sources[{i}]")
        for field in ("claim", "url", "publisher", "reference_title"):
            if not isinstance(source.get(field), str) or len(source[field].strip()) < 5:
                raise ValueError(f"{key}: fact_sources[{i}].{field} is missing")
        parsed = urlsplit(source["url"])
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host:
            raise ValueError(f"{key}: fact source must be an HTTPS citation")
        if any(host == domain or host.endswith("." + domain) for domain in REJECTED_HOSTS):
            raise ValueError(f"{key}: animal video/social footage is not an independent scientific citation")
    if len({s["url"].strip() for s in sources}) != len(sources):
        raise ValueError(f"{key}: duplicate scientific URLs")
    if len({s["publisher"].strip().casefold() for s in sources}) < 2:
        raise ValueError(f"{key}: require two independent scientific publishers")
    script = str(entry.get("script") or "").strip()
    if not script:
        raise ValueError(f"{key}: empty narration script")
    # Mechanical anti-compilation gate: editorial review remains mandatory.
    descriptive = (
        r"\b(?:agora|depois|em seguida) (?:ele|ela|o gato|a gata) "
        r"(?:anda|olha|caminha|aparece)\b",
        r"\b(?:aqui vemos|na próxima cena|o vídeo mostra)\b",
    )
    if any(re.search(pattern, script, flags=re.IGNORECASE) for pattern in descriptive):
        raise ValueError(f"{key}: chronological clip-description narration is forbidden")
    plan = entry.get("visual_plan")
    if not isinstance(plan, list) or not 5 <= len(plan) <= 7:
        raise ValueError(f"{key}: visual_plan must contain 5-7 factual blocks")
    roles = [block.get("story_role") for block in plan if isinstance(block, dict)]
    if len(roles) != len(plan) or roles[0] != "hook" or roles[-1] != "payoff":
        raise ValueError(f"{key}: visual_plan must start with hook and end with payoff")
    if "action" not in roles or not ({"explanation", "twist"} & set(roles)):
        raise ValueError(f"{key}: visual_plan lacks action or biological explanation")
    if any(not isinstance(block.get("scene"), str) or not block["scene"].strip()
           or not isinstance(block.get("tags"), list) or not block["tags"]
           for block in plan):
        raise ValueError(f"{key}: each visual block needs scene and source tags")
    normalized = lambda value: re.sub(r"\s+", " ", value).strip()
    if normalized(" ".join(str(block.get("text") or "") for block in plan)) != normalized(script):
        raise ValueError(f"{key}: visual_plan text does not exactly cover script")


def validate_batch(batch):
    if not isinstance(batch, dict) or not batch:
        raise ValueError("WildVox daily must be a nonempty candidate mapping")
    for key, entry in batch.items():
        if not isinstance(entry, dict):
            raise ValueError(f"{key}: invalid daily entry")
        validate_entry(key, entry)


if __name__ == "__main__":
    filename = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("configs/daily.json")
    try:
        validate_batch(json.loads(filename.read_text(encoding="utf-8")))
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"WildVox curiosity editorial gate FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
    print("WildVox curiosity fact-sheet structural gate passed; independent fact and visual review still required.")

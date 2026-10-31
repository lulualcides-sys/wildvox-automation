"""Allocate unique, semantically tagged footage to measured Kokoro speech blocks.

A long spoken block may need several short, relevant clips. Do not demand that
one source cover the entire block before allocating its other clips. All media
must be used once, with no untagged filler or synthetic looping.
"""
from math import ceil


def plan_semantic_shots(local, blocks, max_shot, max_freeze, key):
    n = len(local)
    if not blocks or n < len(blocks):
        raise RuntimeError(f"{key}: too few unique assets for spoken blocks")
    if n > 12:
        raise RuntimeError(f"{key}: more than 12 unique visual assets")
    photo_only = all(item[1] == "image" for item in local)
    if not photo_only and n < 8:
        raise RuntimeError(f"{key}: fewer than eight unique video-first assets")
    if any(not block.get("tags") for block in blocks):
        raise RuntimeError(f"{key}: spoken block lacks semantic tags")

    durations = [float(block["duration"]) for block in blocks]
    if any(d <= 0 for d in durations):
        raise RuntimeError(f"{key}: invalid Kokoro block duration")
    minimum = [max(1, ceil((d - 0.000001) / max_shot)) for d in durations]
    maximum = [min(n, max(1, int(d / 1.8))) for d in durations]
    if any(lo > hi for lo, hi in zip(minimum, maximum)) or sum(minimum) > n:
        raise RuntimeError(f"{key}: insufficient footage to keep every shot <= {max_shot}s")

    compositions = []

    def counts_for_blocks(index, remaining, counts):
        if index == len(blocks):
            if remaining == 0:
                compositions.append(tuple(counts))
            return
        low = minimum[index]
        high = min(maximum[index], remaining)
        rest_min = sum(minimum[index + 1:])
        rest_max = sum(maximum[index + 1:])
        for count in range(low, high + 1):
            if rest_min <= remaining - count <= rest_max:
                counts_for_blocks(index + 1, remaining - count, counts + [count])

    counts_for_blocks(0, n, [])
    # Prefer readable 3-6 second shots, but never trade semantic correctness
    # for cadence. The matching algorithm below is the actual approval gate.
    compositions.sort(key=lambda counts: sum(
        (dur / count - 4.5) ** 2 for dur, count in zip(durations, counts)
    ))

    def compatible(item, block, seconds):
        wanted = {str(t).strip().lower() for t in block.get("tags", [])}
        actual = {str(t).strip().lower() for t in item[2].get("tags", [])}
        if not (wanted & actual):
            return False
        if item[1] == "image":
            return True
        available = float(item[2].get("_duration", 0))
        return available + max_freeze + 0.000001 >= seconds

    for counts in compositions:
        slots = [(i, durations[i] / count) for i, count in enumerate(counts)
                 for _ in range(count)]
        adjacency = []
        for block_index, seconds in slots:
            possible = [j for j, item in enumerate(local)
                        if compatible(item, blocks[block_index], seconds)]
            if not possible:
                break
            possible.sort(key=lambda j: (
                local[j][1] != "video",
                int(local[j][2].get("_source_index", j))
            ))
            adjacency.append(possible)
        if len(adjacency) != n:
            continue

        owner = [-1] * n

        def augment(slot_index, seen):
            for asset_index in adjacency[slot_index]:
                if asset_index in seen:
                    continue
                seen.add(asset_index)
                previous = owner[asset_index]
                if previous < 0 or augment(previous, seen):
                    owner[asset_index] = slot_index
                    return True
            return False

        order = sorted(range(n), key=lambda i: len(adjacency[i]))
        if not all(augment(i, set()) for i in order):
            continue

        assigned = [None] * n
        for asset_index, slot_index in enumerate(owner):
            if slot_index >= 0:
                assigned[slot_index] = local[asset_index]
        if any(item is None for item in assigned):
            continue
        return [(item, seconds, blocks[block_index])
                for item, (block_index, seconds) in zip(assigned, slots)]

    raise RuntimeError(
        f"{key}: cannot match all {n} unique assets to Kokoro blocks "
        "within shot-length and source-duration limits. Replace or re-tag "
        "verified footage; never use unrelated filler or freeze a clip."
    )

def validate_editorial_tags(batch):
    """Reject index-only source/scene labels before expensive source downloads.

    This is a structural guard, NOT visual proof that a clip depicts its tag.
    Tags must still be checked against actual footage by an independent editor.
    """
    import re

    failures = []
    for key, entry in batch.items():
        blocks = entry.get("visual_plan") or []
        sources = entry.get("sources") or []
        wanted = []
        available = []

        for kind, records, destination in (
            ("block", blocks, wanted), ("source", sources, available)
        ):
            for index, record in enumerate(records):
                tags = {str(t).strip().lower() for t in record.get("tags", []) if str(t).strip()}
                if not tags:
                    failures.append(f"{key}: {kind} {index} lacks semantic tags")
                for tag in tags:
                    # e.g. 'european_mant_3' or 'bald_eagle_fe_4':
                    # the tag is only a truncated prefix of the candidate key.
                    match = re.fullmatch(r"(.+)_([0-9]+)", tag)
                    if match and key.startswith(match.group(1)):
                        failures.append(f"{key}: {kind} {index} has numbered placeholder tag {tag}")
                destination.append(tags)

        for index, tags in enumerate(wanted):
            if not any(tags & source_tags for source_tags in available):
                failures.append(f"{key}: block {index} has no tagged source")
        for index, tags in enumerate(available):
            if not any(tags & block_tags for block_tags in wanted):
                failures.append(f"{key}: source {index} is not relevant to any spoken block")

        # Local tag overlap is not enough: two narration blocks can both
        # depend on the same sole clip. Require a distinct source for each
        # block before downloading media. This is a necessary (not sufficient)
        # condition; Kokoro durations and shot limits are checked at render.
        adjacency = [
            [source_index for source_index, source_tags in enumerate(available)
             if block_tags & source_tags]
            for block_tags in wanted
        ]
        assigned = {}

        def match_block(block_index, seen):
            for source_index in adjacency[block_index]:
                if source_index in seen:
                    continue
                seen.add(source_index)
                previous = assigned.get(source_index)
                if previous is None or match_block(previous, seen):
                    assigned[source_index] = block_index
                    return True
            return False

        if not all(match_block(index, set()) for index in
                   sorted(range(len(wanted)), key=lambda i: len(adjacency[i]))):
            failures.append(
                f"{key}: cannot assign a distinct source to every spoken block"
            )
    if failures:
        raise ValueError("Semantic tag preflight failed (not visual approval):\n" + "\n".join(failures))
    return True


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument("--check-config", required=True)
    args = parser.parse_args()
    validate_editorial_tags(json.loads(Path(args.check_config).read_text(encoding="utf-8")))
    print("Semantic tag preflight passed (not independent visual approval).")

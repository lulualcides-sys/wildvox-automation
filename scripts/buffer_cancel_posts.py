#!/usr/bin/env python3
"""Delete specific SCHEDULED Buffer posts by ID (never touches sent posts)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_buffer as pb  # noqa: E402


def main(ids):
    names = pb.graphql('query { __type(name: "Mutation") { fields { name args { name type { name kind ofType { name } } } } } }')
    fields = {f["name"]: f for f in names["__type"]["fields"]}
    print("DELETE-LIKE MUTATIONS:", [n for n in fields if "delete" in n.lower() or "remove" in n.lower()])
    f = fields.get("deletePost")
    if not f:
        raise RuntimeError("Buffer API has no deletePost mutation")
    arg = f["args"][0]
    tname = arg["type"]["name"] or (arg["type"].get("ofType") or {}).get("name")
    print("deletePost arg:", arg["name"], tname)
    for pid in ids:
        if arg["name"] == "input":
            q = "mutation($i: " + tname + "!) { deletePost(input: $i) { __typename ... on MutationError { message } } }"
            r = pb.graphql(q, {"i": {"id": pid}})
        else:
            q = "mutation($i: " + tname + "!) { deletePost(" + arg["name"] + ": $i) { __typename } }"
            r = pb.graphql(q, {"i": pid})
        print("DELETED?", pid, json.dumps(r))


if __name__ == "__main__":
    main(sys.argv[1:])

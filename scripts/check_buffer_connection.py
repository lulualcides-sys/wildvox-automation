#!/usr/bin/env python3
"""Read-only Buffer connectivity diagnostic. Never logs API keys."""
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def gql(query):
    token = os.environ["BUFFER_API_KEY"]
    req = Request(
        "https://api.buffer.com",
        method="POST",
        data=json.dumps({"query": query}).encode("utf-8"),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as error:
        print("BUFFER_HTTP_STATUS=" + str(error.code))
        raise RuntimeError("Buffer API credential/auth check failed") from None
    except URLError:
        raise RuntimeError("Buffer API network unavailable") from None
    if payload.get("errors"):
        codes = [
            item.get("extensions", {}).get("code", "GRAPHQL_ERROR")
            for item in payload["errors"]
        ]
        print("BUFFER_GRAPHQL_ERRORS=" + ",".join(str(x) for x in codes))
        raise RuntimeError("Buffer read-only query failed")
    return payload["data"]


def main():
    flag = os.environ.get("WILDVOX_BUFFER_ENABLED") == "true"
    token = os.environ.get("BUFFER_API_KEY", "")
    print("WILDVOX_BUFFER_ENABLED=" + ("true" if flag else "false_or_missing"))
    print("BUFFER_API_KEY=" + ("present" if token else "missing"))
    if not token:
        return

    organizations = gql("query { account { organizations { id } } }")["account"]["organizations"]
    found = []
    for organization in organizations:
        org_id = json.dumps(organization["id"])
        channels = gql(
            "query { channels(input: {organizationId: " + org_id +
            "}) { id name displayName service isQueuePaused } }"
        )["channels"]
        for channel in channels:
            is_tiktok = str(channel.get("service", "")).lower() == "tiktok"
            names = (str(channel.get("name") or "") + " " + str(channel.get("displayName") or "")).lower()
            if is_tiktok and "wildvox" in names:
                found.append(channel)

    print("BUFFER_AUTHENTICATED=true")
    print("WILDVOX_TIKTOK_CHANNEL_COUNT=" + str(len(found)))
    if found:
        print("WILDVOX_TIKTOK_QUEUE_PAUSED=" + str(found[0].get("isQueuePaused", "unknown")).lower())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("DIAGNOSTIC_ERROR=" + str(exc), file=sys.stderr)
        sys.exit(1)

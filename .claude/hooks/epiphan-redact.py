#!/usr/bin/env python3
# PostToolUse: mask stream keys and credentialed stream URLs in Epiphan read-tool output
# before the model (or a screen recording) sees them. get_stream_endpoint(s) returns
# StreamingKey in plain text, and channel settings can carry keys in publisher settings.
# Keeps host + app so the agent can still reason about destinations: rtmp://host/app/••••
# Walks the JSON structurally, including JSON embedded in MCP text content.
import json, re, sys

MASK = "••••"
# Field names/labels whose values are secrets. Not StreamID: that's the endpoint's ID, needed for writes.
SECRET = re.compile(r"stream_?key|streamingkey|\bkey\b|password|passphrase|passwd|secret|token", re.IGNORECASE)
USERINFO_RE = re.compile(r"((?:rtmps?|srt|rtsp)://)[^/@\s]+@", re.IGNORECASE)        # user:pass@
RTMP_PATH_RE = re.compile(r"(rtmps?://[^/\s]+/[^/\s?]+)/\S+", re.IGNORECASE)          # /app/<key>
QUERY_RE = re.compile(r"([?&](?:streamid|passphrase|password|key|token)=)[^&\s]+", re.IGNORECASE)


def scrub_str(s: str) -> str:
    stripped = s.strip()
    if stripped[:1] in "{[":
        try:
            parsed = json.loads(s)
        except ValueError:
            parsed = None
        if parsed is not None:
            cleaned = scrub(parsed)
            return s if cleaned == parsed else json.dumps(cleaned, ensure_ascii=False)
    s = USERINFO_RE.sub(lambda m: m.group(1) + MASK + "@", s)
    s = RTMP_PATH_RE.sub(lambda m: m.group(1) + "/" + MASK, s)
    return QUERY_RE.sub(lambda m: m.group(1) + MASK, s)


def scrub(node):
    if isinstance(node, dict):
        # settings entries: {"id": "...", "title": "Stream key", "value": "<secret>"}
        labels = " ".join(str(node.get(k, "")) for k in ("id", "title", "name") if isinstance(node.get(k), str))
        secret_entry = "value" in node and SECRET.search(labels)
        out = {}
        for k, v in node.items():
            if isinstance(v, (str, int)) and not isinstance(v, bool) and str(v) and (
                    SECRET.search(k) or (k == "value" and secret_entry)):
                out[k] = MASK
            else:
                out[k] = scrub(v)
        return out
    if isinstance(node, list):
        return [scrub(x) for x in node]
    if isinstance(node, str):
        return scrub_str(node)
    return node


def main() -> None:
    event = json.load(sys.stdin)
    response = event.get("tool_response")
    if response is None:
        return
    cleaned = scrub(response)
    if cleaned == response:
        return  # nothing sensitive: leave the output untouched
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                             "updatedMCPToolOutput": cleaned}}, ensure_ascii=False))


if __name__ == "__main__":
    main()

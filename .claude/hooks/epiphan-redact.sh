#!/usr/bin/env bash
# PostToolUse redactor for the Epiphan MCP server and claude.ai connectors to it (same matcher as the
# write guard; like the guard, it acts on the Epiphan Edge tools it knows and on the device server itself,
# and leaves other Epiphan services alone).
# This hook rewrites the tool's output before Claude sees it:
#   - fields named like a secret (StreamingKey, stream_key, srt.passphrase, password, pin, token, ...) and
#     {"id"/"name"/"key"/"label"/"field": "<secret name>", "value": ...} pairs get the value "[redacted]";
#     a publisher's "stream" field (Pearl's name for the RTMP stream key) is masked when it sits next to a
#     url, username or password field;
#   - streaming URLs (rtmp*, srt, rtsp, rist) keep only scheme + host; http(s) URLs lose user:password@
#     and their ?query;
#   - "stream key: abc", "api_key=abc", "Bearer abc" style text is masked too, and so is user:password@ in
#     any URL;
#   - an Anthropic API key (sk-ant-api03-..., sk-ant-admin01-...) is masked even bare, with no "key:" in front;
#   - a "[redacted]" already in the text is read as part of the value around it, so typing one in front of a
#     secret can't hide the rest, and redacting twice gives the same text as once.
# JSON is parsed, not pattern-matched, including JSON inside strings. A single text value over 200 KB that
# looks secret-bearing is withheld rather than scanned; whole results that take over 20 s are withheld.
# Best effort: it knows the field names Epiphan uses today, not every way a secret could be written.
# Fails closed: if output looks like it holds a secret but can't be redacted (no jq, an error, or
# too slow), Claude gets a short "withheld" note instead of the original.
input=$(cat)

withhold() {
  printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","updatedToolOutput":"[Epiphan kit: this result was withheld because it %s.]"}}\n' "$1"
  exit 0
}

# Keep these lists in step with .claude/settings.json and epiphan-write-guard.sh (tests/hook-test.sh checks).
KNOWN=" get_devices_in_my_team get_device_info get_device_sources get_system_status_for_devices get_recorder_status_for_devices get_storage_status_for_devices get_channel_settings get_channel_image get_channel_audio_levels get_stream_endpoint get_stream_endpoints get_team_presets get_cms_events_for_device get_cms_events_for_devices get_current_or_next_cms_event_for_device get_current_or_next_cms_events_for_devices get_cms_names_for_devices get_devices_by_cms kb_search kb_fetch batch_recording start_stream_endpoint stop_stream_endpoint create_cms_event update_cms_event delete_cms_event cms_event_action confirm_cms_event_on_device create_stream_endpoint update_stream_endpoint delete_stream_endpoint apply_team_preset switch_device_to_cms batch_reboot batch_firmware_update "
DEVICE_SERVER='^(epiphan([-_].*)?|claude_ai_(.*_)?epiphan([-_]?(mcp|cloud|edge)([-_].*)?)?|plugin_.*epiphan.*)$'

# Which tool is this? Only trusted when "tool_name" appears once, so a copy nested in the tool's input
# can't fake it; otherwise nothing is skipped.
names=$(printf '%s' "$input" | grep -o '"tool_name"[[:space:]]*:[[:space:]]*"[^"]*"')
case "$names" in
  *$'\n'*) ;;
  ?*)
    name=${names%\"}; name=${name##*\"}
    server=${name%__*}; server=${server#mcp__}; tool=${name##*__}
    case "$tool" in get_channel_image|kb_search|kb_fetch) exit 0 ;; esac   # preview images and docs pages never hold your keys
    case "$KNOWN" in
      *" $tool "*) ;;
      *) printf '%s' "$server" | grep -qiE "$DEVICE_SERVER" || exit 0 ;;  # another Epiphan service: not ours to touch
    esac ;;
esac

# Fast path: most outputs (device lists, status) mention nothing secret-like. Skip jq for them.
# (grep exits 1 for "no match"; anything else, like an error, goes on to the full check.)
printf '%s' "$input" | grep -qiE 'key|pass|pwd|pin|psk|pw"|secret|token|auth|cred|bearer|basic|sk-ant-|stream|webhook|:\\*/|u002f|%2f'
[ $? -eq 1 ] && exit 0

if ! command -v jq >/dev/null 2>&1; then
  # Without jq, withhold anything secret-shaped: a field named like a secret ("StreamingKey": ..., "srt.passphrase": ...,
  # "pin": ...), an id/name/label whose value names a secret ("id": "publisher.rtmp.key"), "stream key: ...",
  # "api_key=..." or "Bearer ..." text, an sk-ant-... key, a streaming URL with a path, an https URL with an ingest,
  # live or webhook path, or any URL with user:password@ or a ?query. Words like "Keynote" in an event title don't count.
  printf '%s' "$input" | grep -qiE '"[A-Za-z0-9_. /:-]*(key|stream[ _-]?name|stream[ _-]?id|password|passphrase|passwd|pwd|pw|pin|psk|pass|secret|token|authorization|auth|credentials?)\\*"[[:space:]]*:|"(id|name|key|label|field)\\*"[[:space:]]*:[[:space:]]*\\*"[^"]*(key|password|passphrase|passwd|pwd|pin|psk|secret|token)\\*"|(stream([ _-]|%20)?(key|name)|password|passphrase|passwd|pwd|secret|token|authorization|(^|[^a-z0-9])(key|pin|psk|pass|pw))["'\'']?[[:space:]]*[:=]|bearer[[:space:]]|basic[[:space:]]+[A-Za-z0-9+/=]{8}|(^|[^A-Za-z0-9_])sk-ant-|(rtmp[a-z]*|srt|rtsp|rist):(\\*/){2}[^"[:space:]]*(\\*/|\?)|:(\\*/){2}[^/"[:space:]]*@|https?:(\\*/){2}[^"[:space:]]*(\?|whip|whep|ingest|publish|upload|live|stream|rtmp|srt|push|broadcast|webhook|hooks\.slack|discord(app)?\.com/api/webhooks)|\|[[:space:]]*(stream[ _-]?(key|name|id)|key|password|passphrase|token|secret)[[:space:]]*\|'
  [ $? -eq 1 ] && exit 0
  withhold "may contain stream keys and jq, which hides them, isn't installed (Mac: brew install jq; Linux: install the jq package; Windows: winget install jqlang.jq). Then try again"
fi

budget=${EPIPHAN_REDACT_SECONDS:-20}
tmp=$(mktemp) || withhold "couldn't be checked for stream keys (no temp file)"
trap 'rm -f "$tmp"' EXIT

# shellcheck disable=SC2016  # $-names below are jq variables, not shell ones
{ printf '%s' "$input" 2>/dev/null; } | jq -c '
  # Cheap string checks first: jq 1.6 compiles a regex on every test() call, and a device list has tens of
  # thousands of keys, so the regex runs only on keys that end like a secret name.
  def secret_name:
    type == "string" and (ascii_downcase as $k
      | ($k | endswith("key") or endswith("password") or endswith("passphrase") or endswith("passwd") or endswith("pwd")
            or endswith("pw") or endswith("pin") or endswith("psk") or endswith("pass") or endswith("secret") or endswith("token")
            or endswith("authorization") or endswith("auth") or endswith("credential") or endswith("credentials")
            or (endswith("name") and contains("stream")))
      and (($k | contains("page") or contains("cursor")) | not)
      and ($k | test("^(?:.*[_\\-. /:])?(?:streaming[ _-]?key|stream[ _-]?key|stream[ _-]?name|api[ _-]?key|private[ _-]?key|key|password|passphrase|passwd|pwd|pw|pin|psk|pass|secret|token|authorization|auth|credentials?)$")));
  def stream_id_name: type == "string" and (ascii_downcase as $k | ($k | endswith("id") and contains("stream")) and ($k | test("^(?:.*[_\\-. /:])?stream[ _-]?id$")));
  def uuid: type == "string" and test("^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$"; "i");
  def table_col: gsub("^\\s+|\\s+$"; "") | ascii_downcase | gsub("[ -]+"; "_");
  def table_secret_col: table_col | (secret_name or stream_id_name);
  def scrub_tables:  # a pipe table whose header names a secret column: mask that column (a stream ID only if not a UUID)
    (if test("\n") then "\n" else "\\n" end) as $sep
    | if ([split($sep)[] | select(test("^\\s*\\|"))] | length) < 2 then . else
        reduce (split($sep)[]) as $l ({out: [], cols: null};
          if ($l | test("^\\s*\\|") | not) then .cols = null | .out += [$l]
          elif ($l | test("^\\s*\\|?[\\s:|-]+$")) then .out += [$l]
          else
            ($l | sub("^\\s*\\|"; "") | sub("\\|\\s*$"; "") | split("|")) as $cells
            | if .cols == null then .cols = [range(0; $cells | length) | select($cells[.] | table_secret_col)]
                | .ids = [range(0; $cells | length) | select($cells[.] | table_col | stream_id_name)] | .out += [$l]
              elif (.cols | length) == 0 then .out += [$l]
              else .cols as $c | .ids as $ids
                | .out += ["|" + ([range(0; $cells | length) as $i
                    | if any($c[]; . == $i) and ($cells[$i] | test("\\S"))
                         and ((any($ids[]; . == $i) and ($cells[$i] | gsub("^\\s+|\\s+$"; "") | uuid)) | not) then " [redacted] " else $cells[$i] end] | join("|")) + "|"]
              end
          end)
        | .out | join($sep)
      end;
  def mask: if type == "boolean" or type == "null" or . == "" then . else "[redacted]" end;
  # A "[redacted]" already in the text is read as part of the value around it, so the whole value is masked
  # again; masks with nothing secret-like after them (a quote, a space, punctuation) are already done.
  def M: "\\[redacted\\]";
  def masks: "(?:\(M))+(?![\\w/.~%+=&:@?#\\[-])";
  def thru(c): "(?:\(masks)|(?:\(M)|\(c))*)";  # a value of c characters, read through any masks in it
  def scrub_text:
    if test("://|:\\\\/\\\\/|key|pass|pwd|pin|psk|\\bpw\\b|secret|token|auth|cred|bearer|basic|stream|webhook|sk-ant-"; "i") | not then .
    elif length > 200000 then "[Epiphan kit: a long text value was withheld because it was too long to check for stream keys]"
    else
      (if test("\\|") then scrub_tables else . end)
      | gsub("(?<p>\\b[a-z][a-z0-9+.-]*(?:://|:\\\\/\\\\/))(?:\(M)|[^/?#\\s\"<>()\\[\\]])*@"; "\(.p)"; "i")  # user:password@, any scheme
      | gsub("(?<p>\\b(?:rtmp[a-z]*|srt|rtsp|rist)://)(?<h>[^/?#\\s\"'"'"'<>()\\[\\],@]+)(?<r>[/?#]\(thru("[^\\s\"'"'"'<>()\\[\\],]")))?";
           "\(.p)\(.h)\(if .r then "/[redacted]" else "" end)"; "i")
      | gsub("(?<p>\\b(?:rtmp[a-z]*|srt|rtsp|rist|https?):\\\\/\\\\/)(?<h>[^\\\\\\s\"'"'"'<>]+)(?<r>\\\\/[^\\s\"'"'"'<>]*)";
           "\(.p)\(.h)\\/[redacted]"; "i")
      | gsub("(?<p>\\b(?:https?|wss?|s?ftps?)://)(?<h>[^/?#\\s\"'"'"'<>()\\[\\],@]+)(?<path>/\(thru("[^?#\\s\"'"'"'<>()\\[\\],]")))?(?<q>\\?\(thru("[^\\s\"'"'"'<>()\\[\\],]")))?";
           "\(.p)\(.h)\(if .path == null then "" elif ((.h + .path) | test("whip|whep|ingest|publish|upload|live|stream|rtmp|srt|push|broadcast|webhook|hooks\\.slack|discord(?:app)?\\.com/api/webhooks"; "i")) then "/[redacted]" else .path end)\(if .q then "?[redacted]" else "" end)"; "i")
      | gsub("(?<k>[\"'"'"']?\\b(?:streaming[ _-]?key|stream(?:[ _-]|%20)?key|stream(?:[ _-]|%20)?name|password|passphrase|passwd|pwd|secret|client[_-]?secret|access[_-]?token|token|authorization|(?:x[_-])?api[_-]?key|private[_-]?key|pass|pin|psk|pw|key)[\"'"'"']?\\s*[:=]\\s*)(?:(?<dq>\"(?:[^\"\\\\\\n]|\\\\.)*\")|(?<sq>'"'"'(?:[^'"'"'\\\\\\n]|\\\\.)*'"'"')|(?<oq>[\"'"'"'])?(?<s>(?:bearer|basic)\\s+)?(?:\(masks)|(?:\(M)|[^\\s\"'"'"',;}\\]|])+))";
           "\(.k)\(if .dq then "\"[redacted]\"" elif .sq then "'"'"'[redacted]'"'"'" else "\(.oq // "")\(.s // "")[redacted]" end)"; "i")
      | gsub("(?<s>\\b(?:bearer|basic)\\s+)(?:\(masks)|[\\w.~+/=-]*\(M)(?:\(M)|[\\w.~+/=-])*|(?=[\\w.~+/-]*[0-9+/=])[\\w.~+/-]+=*|[\\w.~+/-]{20,}=*)";  # a token: a digit, +, / or =, or 20+ characters
           "\(.s)[redacted]"; "i")
      | gsub("\\bsk-ant-(?:\(M)|[\\w-])+"; "[redacted]"; "i")  # an Anthropic API key, even bare
    end;
  def redact:
    if type == "object" then
      (if has("value") and ([.id, .name, .key, .label, .field] | any(secret_name or stream_id_name)) then .value |= mask else . end)
      # The "stream" field of a publisher is the RTMP stream key when it sits next to url/username/password
      # (Pearl publisher settings); a bare "stream": true flag or a stream name without a URL is left alone.
      | (if (has("stream") or has("Stream") or has("STREAM"))
            and ([keys_unsorted[] | ascii_downcase] | any(. == "url" or . == "username" or . == "password")) then
           with_entries(if (.key | ascii_downcase) == "stream" and (.value | type) == "string" and .value != "" then .value |= mask else . end)
         else . end)
      | has("value") as $pair
      | with_entries(
          if (.key | secret_name) and (($pair | not) or (.value | type) != "string" or (.value | secret_name | not)) then .value |= mask
          elif (.key | stream_id_name) and (.value | uuid | not) then .value |= mask  # Epiphan StreamID is a UUID: kept
          else .value |= redact end)
    elif type == "array" then map(redact)
    elif type == "string" then
      if test("^\\s*[\\[{]") then
        (try fromjson catch null) as $p
        | if ($p | type) == "object" or ($p | type) == "array" then
            ($p | redact) as $r | if $r == $p then . else $r | tojson end
          else scrub_text end
      else scrub_text end
    else . end;
  (.tool_name // "") as $name
  | if ($name | split("__") | last | test("^(get_channel_image|kb_search|kb_fetch)$")) then empty else . end
  | .tool_response as $orig
  | ($orig | redact) as $new
  | if $new == $orig then empty
    else {hookSpecificOutput: {hookEventName: "PostToolUse", updatedToolOutput: $new}} end
' > "$tmp" 2>/dev/null &
pid=$!

# Wait for jq, but not forever: a hook that times out has its output dropped, which would let the
# original (unredacted) result through.
ticks=$((budget * 10))
while kill -0 "$pid" 2>/dev/null && [ "$ticks" -gt 0 ]; do sleep 0.1; ticks=$((ticks - 1)); done
if kill -0 "$pid" 2>/dev/null; then
  kill "$pid" 2>/dev/null
  wait "$pid" 2>/dev/null
  status=124
else
  wait "$pid" 2>/dev/null; status=$?
fi

[ "$status" -eq 0 ] && { cat "$tmp"; exit 0; }
[ "$status" -eq 124 ] && withhold "couldn't be checked for stream keys in time. Ask for a narrower query, for example one device"
withhold "couldn't be checked for stream keys"

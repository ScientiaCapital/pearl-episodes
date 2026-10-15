#!/usr/bin/env bash
# Tests for the hooks in .claude/hooks/ and the permission rules in .claude/settings.json.
# Adapted from the Epiphan Edge Claude Kit v1.1.3 (tests/hook-test.sh): the write guard, redactor and shared
# redaction corpus checks are unchanged; the kit-only checks (its README, commands and installers) are dropped,
# the two allow-list checks look at mcp__ rules only (this repo also allows a few exact Bash commands), and a
# section for check-secrets.sh is added at the end.
# Write guard: reads pass silently, everything else must "ask" (or "deny" in bypass mode).
# Redactor: stream keys and credentialed URLs never reach the model.
set -u -o pipefail
cd "$(dirname "$0")/.." || exit 1
unset EPIPHAN_READ_ONLY  # the read-only switch is tested on its own below
hook=.claude/hooks/epiphan-write-guard.sh
redact=.claude/hooks/epiphan-redact.sh
fails=0
ok() { echo "ok   $1"; }
bad() { echo "FAIL $1"; fails=$((fails + 1)); }

expect() { # expect <pass|ask|deny> <label> <stdin>
  local out code
  out=$(printf '%s' "$3" | bash "$hook"); code=$?
  if [ "$1" = pass ]; then
    [ "$code" -eq 0 ] && [ -z "$out" ] && { ok "pass  $2"; return; }
  else
    [ "$code" -eq 0 ] && printf '%s' "$out" | jq -e --arg d "$1" '.hookSpecificOutput.permissionDecision == $d' >/dev/null 2>&1 \
      && { ok "$1   $2"; return; }
  fi
  bad "$1 $2 (exit=$code, out=$out)"
}

# Prefixes the Epiphan Edge tools appear under: the kit's server, the claude.ai connector Epiphan's guide names,
# and made-up "Epiphan Cloud" connector names like the ones a team might add.
prefixes="epiphan claude_ai_Epiphan_MCP claude_ai_Epiphan_Cloud claude_ai_TEST_Epiphan_Cloud claude_ai_Lab_Epiphan_Cloud"
for p in $prefixes; do
  expect pass "$p read"          "{\"tool_name\":\"mcp__${p}__get_devices_in_my_team\"}"
  expect pass "$p kb"            "{\"tool_name\":\"mcp__${p}__kb_search\"}"
  expect ask  "$p write"         "{\"tool_name\":\"mcp__${p}__batch_recording\"}"
  expect ask  "$p reboot"        "{\"tool_name\":\"mcp__${p}__batch_reboot\"}"
  expect ask  "$p stop"          "{\"tool_name\":\"mcp__${p}__stop_stream_endpoint\"}"
  expect ask  "$p preset"        "{\"tool_name\":\"mcp__${p}__apply_team_preset\"}"
  expect ask  "$p future tool"   "{\"tool_name\":\"mcp__${p}__some_new_tool\"}"
  # Only the tools on the read list pass: a new tool named like a read still asks.
  expect ask  "$p future get_"   "{\"tool_name\":\"mcp__${p}__get_and_reset_device\"}"
  expect ask  "$p future kb_"    "{\"tool_name\":\"mcp__${p}__kb_publish\"}"
done
# A tool_name that isn't a string can't be checked, so it's blocked.
expect deny "numeric tool_name"     '{"tool_name":123}'
expect deny "null tool_name"        '{"tool_name":null}'
expect deny "array tool_name"       '{"tool_name":["mcp__epiphan__get_device_info"]}'
expect deny "object tool_name"      '{"tool_name":{"name":"mcp__epiphan__get_device_info"}}'
expect deny "missing tool_name"     '{"tool_input":{}}'
expect deny "boolean tool_name"     '{"tool_name":true,"permission_mode":"default"}'

# EPIPHAN_READ_ONLY=1 denies every Epiphan Edge write, in every mode; reads and other services are unchanged.
for p in $prefixes; do
  EPIPHAN_READ_ONLY=1 expect deny "read-only: $p write"       "{\"tool_name\":\"mcp__${p}__batch_recording\"}"
  EPIPHAN_READ_ONLY=1 expect deny "read-only: $p reboot"      "{\"tool_name\":\"mcp__${p}__batch_reboot\"}"
  EPIPHAN_READ_ONLY=1 expect deny "read-only: $p future tool" "{\"tool_name\":\"mcp__${p}__get_and_reset_device\"}"
  EPIPHAN_READ_ONLY=1 expect pass "read-only: $p read"        "{\"tool_name\":\"mcp__${p}__get_stream_endpoints\"}"
done
EPIPHAN_READ_ONLY=1 expect deny "read-only: known write on an odd connector" '{"tool_name":"mcp__claude_ai_Epiphan_Fleet__batch_reboot"}'
EPIPHAN_READ_ONLY=1 expect deny "read-only: write in acceptEdits mode"     '{"permission_mode":"acceptEdits","tool_name":"mcp__epiphan__start_stream_endpoint"}'
EPIPHAN_READ_ONLY=1 expect deny "read-only: unreadable call"               'not json "tool_name":"mcp__epiphan__batch_reboot"'
EPIPHAN_READ_ONLY=1 expect pass "read-only: other Epiphan service"         '{"tool_name":"mcp__claude_ai_Epiphan_Knowledge__search"}'
EPIPHAN_READ_ONLY=0 expect ask  "EPIPHAN_READ_ONLY=0 still asks"           '{"tool_name":"mcp__epiphan__batch_recording"}'
EPIPHAN_READ_ONLY='' expect ask  "empty EPIPHAN_READ_ONLY still asks"       '{"tool_name":"mcp__epiphan__batch_recording"}'
expect ask "pretty-printed write" $'{\n  "tool_name": "mcp__epiphan__batch_firmware_update",\n  "tool_input": {}\n}'
expect deny "empty input is blocked"     ''
expect ask  "malformed input still asks" 'not json "tool_name":"mcp__epiphan__batch_reboot"'
expect deny "unreadable call is blocked" 'not json'
expect ask "odd tool name stays valid JSON" '{"tool_name":"mcp__epiphan__evil\\\"x\\\\"}'
# A read name with a stray character isn't the read on the list; the raw name decides, not the cleaned-up one.
expect ask  "read name with a stray character" '{"tool_name":"mcp__epiphan__get_device_info."}'
expect ask  "read name with a semicolon"       '{"tool_name":"mcp__epiphan__get_device_info;"}'
# EPIPHAN_READ_ONLY with stray whitespace (easy in PowerShell) is still on.
EPIPHAN_READ_ONLY=' 1 ' expect deny "read-only with whitespace"   '{"tool_name":"mcp__epiphan__batch_recording"}'
EPIPHAN_READ_ONLY='TRUE ' expect deny "read-only, upper and space" '{"tool_name":"mcp__epiphan__batch_recording"}'
EPIPHAN_READ_ONLY=' 0 ' expect ask  "read-only ' 0 ' still asks"   '{"tool_name":"mcp__epiphan__batch_recording"}'
# Disruptive writes carry the louder warning (the same set Fleetwatch's tool_policy.yaml calls disruptive).
disruptive() { # disruptive <tool>
  local out
  out=$(printf '{"tool_name":"mcp__epiphan__%s"}' "$1" | bash "$hook")
  if printf '%s' "$out" | jq -e '.hookSpecificOutput.permissionDecision == "ask" and (.hookSpecificOutput.permissionDecisionReason | startswith("DISRUPTIVE"))' >/dev/null 2>&1; then
    ok "DISRUPTIVE warning on $1"; else bad "no DISRUPTIVE warning on $1: $out"; fi
}
for t in batch_reboot batch_firmware_update stop_stream_endpoint delete_cms_event delete_stream_endpoint apply_team_preset \
         switch_device_to_cms update_cms_event cms_event_action; do disruptive "$t"; done
out=$(printf '{"tool_name":"mcp__epiphan__batch_recording"}' | bash "$hook")
if printf '%s' "$out" | jq -e '.hookSpecificOutput.permissionDecisionReason | startswith("WRITE")' >/dev/null 2>&1; then ok "WRITE warning on batch_recording"; else bad "batch_recording warning: $out"; fi

# Other Epiphan services (docs, CRM, ...) are left to normal permissions; Epiphan Edge tools are guarded under
# any connector name, and unknown tools only on the device server itself.
expect pass "other Epiphan service, unknown tool"  '{"tool_name":"mcp__claude_ai_Epiphan_Knowledge__search"}'
expect ask  "known write on an odd connector name" '{"tool_name":"mcp__claude_ai_Epiphan_Fleet__batch_reboot"}'
expect ask  "unknown write on a device connector"  '{"tool_name":"mcp__claude_ai_EpiphanCloud__new_thing"}'
expect ask  "unknown write on epiphan-eu"          '{"tool_name":"mcp__epiphan-eu__new_thing"}'

# Bypass mode skips "ask", so writes must be denied there. Reads still pass.
for m in default acceptEdits auto dontAsk plan; do
  expect ask "write in $m mode" "{\"permission_mode\":\"$m\",\"tool_name\":\"mcp__epiphan__batch_recording\"}"
done
expect deny "write in bypass mode"         '{"permission_mode":"bypassPermissions","hook_event_name":"PreToolUse","tool_name":"mcp__epiphan__batch_recording","tool_input":{}}'
expect deny "reboot in bypass mode"        '{"permission_mode":"bypassPermissions","tool_name":"mcp__claude_ai_Epiphan_MCP__batch_reboot"}'
expect deny "future tool in bypass mode"   '{"permission_mode":"bypassPermissions","tool_name":"mcp__epiphan__some_new_tool"}'
expect pass "read in bypass mode"          '{"permission_mode":"bypassPermissions","tool_name":"mcp__epiphan__get_stream_endpoints"}'
# A copy of tool_name or permission_mode nested in the tool's input must not decide anything, in any key order.
expect ask  "nested read name before a write"   '{"tool_input":{"settings":{"tool_name":"mcp__epiphan__get_x"}},"tool_name":"mcp__epiphan__apply_team_preset"}'
expect deny "nested default before real bypass" '{"tool_input":{"permission_mode":"default"},"permission_mode":"bypassPermissions","tool_name":"mcp__epiphan__batch_reboot"}'
expect ask  "nested bypass text, default mode"  '{"permission_mode":"default","tool_name":"mcp__epiphan__batch_recording","tool_input":{"note":"bypassPermissions"}}'

# Redactor: secret fields and credentialed URLs are masked in every output shape; clean output passes untouched.
inner='{"streams":[{"RTMP":{"StreamingKey":"FAKEKEY123","URL":"rtmps://ingest.example.com:1936/meeting/FAKEPATH9"}},{"x":"srt://u:FAKEPW@h.example:9000?passphrase=FAKEPASS"}],"settings":[{"id":"stream_key","value":"FAKEID7"}]}'
for shape in text object; do
  if [ "$shape" = text ]; then in=$(jq -cn --arg t "$inner" '{tool_name:"mcp__epiphan__get_stream_endpoints",tool_response:[{type:"text",text:$t}]}')
  else in=$(jq -cn --argjson o "$inner" '{tool_name:"mcp__claude_ai_Epiphan_MCP__get_stream_endpoints",tool_response:$o}'); fi
  out=$(printf '%s' "$in" | bash "$redact")
  if printf '%s' "$out" | jq -e '.hookSpecificOutput.hookEventName == "PostToolUse" and (.hookSpecificOutput.updatedToolOutput != null)' >/dev/null 2>&1 \
     && ! printf '%s' "$out" | grep -q 'FAKE' && printf '%s' "$out" | grep -q 'ingest.example.com:1936/\[redacted\]'; then
    ok "redacts keys and URLs ($shape output)"
  else bad "redaction ($shape output): $out"; fi
done
# More shapes a key can hide in. Each must come out with no FAKE left in it.
redacts() { # redacts <label> <inner text>  (wrapped as an MCP text block)
  local out
  out=$(jq -cn --arg t "$2" '{tool_name:"mcp__epiphan__get_stream_endpoints",tool_response:[{type:"text",text:$t}]}' | bash "$redact")
  if [ -n "$out" ] && ! printf '%s' "$out" | grep -q FAKE; then ok "redacts $1"; else bad "redaction misses $1: ${out:-unchanged}"; fi
}
redacts "escaped slashes"        '{"url":"rtmp:\/\/a.example\/live2\/FAKE1"}'
redacts "JSON inside a string"   '{"data":"{\"StreamingKey\":\"FAKE2\"}"}'
redacts "python-style text"      "{'stream_key': 'FAKE3'}"
redacts "prose"                  'Stream key: FAKE4'
redacts "field named key"        '{"server":"rtmp://h/app","key":"FAKE5"}'
redacts "access_token"           '{"access_token":"FAKE6"}'
redacts "non-string values"      '{"stream_key":7,"password":{"v":"FAKE7"}}'
redacts "value before id"        '{"value":"FAKE8","id":"stream_key"}'
redacts "name/value pair"        '{"name":"password","value":"FAKE9"}'
redacts "password with @"        '{"u":"rtmp://user:p@FAKE10@host/app"}'
redacts "https credentials"      '{"u":"https://user:FAKE11@host.example/x?cid=FAKE12"}'
redacts "uppercase / rtmpt"      '{"a":"RTMP://h/app/FAKE13","b":"rtmpt://h/app/FAKE14"}'
redacts "Authorization header"   '{"headers":{"Authorization":"Bearer FAKE15"}}'
redacts "key in an array"        '{"stream_key":["FAKE16"]}'
redacts "SRT streamid field"     '{"streamid":"FAKE19"}'
redacts "stream_name field"      '{"stream_name":"FAKE20"}'
redacts "WHIP ingest path"       '{"u":"https://whip.example/whip/endpoint/FAKE21"}'
redacts "table with a key column" "$(printf '| Name | Stream key |\n|---|---|\n| YT | FAKE22 |')"
redacts "non-UUID StreamID"      '{"StreamID":"live/FAKE23"}'
# Shapes a devil's-advocate review found (v1.1.2): a Pearl publisher's "stream" field next to its url/password,
# dotted or spaced secret names, label/value pairs, short names, /-escaped URLs and webhook paths.
redacts "publisher stream field"   '{"url":"rtmp://a.example/live2","stream":"FAKE50","username":"","password":""}'
redacts "Stream field, capitalized" '{"URL":"rtmp://x.example:1935/app","Stream":"FAKE51"}'
redacts "dotted secret name"       '{"srt.passphrase":"FAKE52"}'
redacts "dotted id/value pair"     '{"settings":[{"id":"publisher.rtmp.key","value":"FAKE53"}]}'
redacts "name with a space"        '{"name":"Stream key","value":"FAKE54"}'
redacts "label/value pair"         '{"label":"Stream key","value":"FAKE55"}'
redacts "pin, pw, psk and pass"    '{"pin":"FAKE56","pw":"FAKE57","psk":"FAKE58","pass":"FAKE59"}'
redacts "unicode-escaped rtmp url" '{"url":"rtmp://a.example/live/FAKE60"}'
redacts "slack webhook path"       '{"hook":"https://hooks.slack.com/services/T0/B0/FAKE61"}'
redacts "discord webhook path"     'https://discord.com/api/webhooks/123/FAKE62'
for t in '{"record":true,"stream":true}' '{"stream":"rtmp"}' '{"stream":"Program","name":"Stream 1"}'; do
  out=$(printf '{"tool_name":"mcp__epiphan__get_device_info","tool_response":%s}' "$t" | bash "$redact")
  if [ -z "$out" ]; then ok "keeps a stream flag or name: $t"; else bad "masked a plain stream field: $t -> $out"; fi
done
out=$(printf '%s' '{"tool_name":"mcp__epiphan__get_device_info","tool_response":{"t":"| Room | Status |\n| Hall | online |","u":"https://panopto.example.edu/Panopto/Pages/Viewer.aspx"}}' | bash "$redact")
if [ -z "$out" ]; then ok "leaves ordinary tables and links alone"; else bad "changed an ordinary table or link: $out"; fi
redacts "pwd and credentials"    '{"pwd":"FAKE17","credentials":"FAKE18"}'
redacts "weak password values"   '{"password":"FAKEsecret","stream_key":"FAKE_token"}'
out=$(printf '%s' '{"tool_name":"mcp__epiphan__get_device_info","tool_response":{"password":"secret","stream_key":"token"}}' | bash "$redact")
if printf '%s' "$out" | jq -e '.hookSpecificOutput.updatedToolOutput == {"password":"[redacted]","stream_key":"[redacted]"}' >/dev/null 2>&1; then
  ok "masks a password whose value looks like a field name"; else bad "weak password value leaked: $out"; fi
out=$(printf '%s' '{"tool_name":"mcp__kb_epiphan__get_stream_endpoints","tool_response":{"stream_key":"FAKE"}}' | bash "$redact")
if [ -n "$out" ] && ! printf '%s' "$out" | grep -q FAKE; then ok "a server named kb_... is still redacted"; else bad "kb_ server skipped redaction"; fi
out=$(printf '%s' '{"tool_name":"mcp__claude_ai_Epiphan_Ai__execute_sql","tool_response":{"key":"ACME-42","auth":"sso"}}' | bash "$redact")
if [ -z "$out" ]; then ok "leaves other Epiphan services' data alone"; else bad "masked another service's data: $out"; fi
big=$(jq -cn '{tool_name:"mcp__epiphan__get_device_info",tool_response:[{type:"text",text:("stream key: FAKE " * 20000)}]}')
start=$SECONDS; out=$(printf '%s' "$big" | bash "$redact")
if [ $((SECONDS - start)) -le 5 ] && [ -n "$out" ] && ! printf '%s' "$out" | grep -q FAKE; then ok "withholds one huge text value quickly"
else bad "huge text value: $((SECONDS - start)) s or leaked"; fi
# Without jq, anything secret-shaped is withheld; ordinary text passes.
nojq=$(mktemp -d)
for b in bash cat grep head printf mktemp rm sleep sed tr wc; do p=$(command -v "$b") && ln -s "$p" "$nojq/$b" 2>/dev/null; done
if PATH="$nojq" "$nojq/bash" -c 'exit 0' 2>/dev/null; then
  for t in '{"Authorization":"Bearer FAKE"}' '{"pwd":"FAKE"}' '"Stream key: FAKE"' '{"url":"https://u:FAKE@h/x?cid=FAKE"}' '{"StreamingKey":"FAKE"}' \
           '"api_key=FAKE"' '"key: FAKE"' '"sent Basic RkFLRUJBU0lD"' '"stream%20key=FAKE"' '{"apiKey":"FAKE"}' '"ftp://u:FAKE@h/x"' \
           '"401 for sk-ant-api03-FAKE"' '{"url":"https://a.example/live/FAKE"}' '"https://hooks.slack.com/services/T0/B0/FAKE"' \
           '{"srt.passphrase":"FAKE"}' '{"id":"publisher.rtmp.key","value":"FAKE"}' '{"pin":"FAKE"}'; do
    out=$(printf '{"tool_name":"mcp__epiphan__get_device_info","tool_response":%s}' "$t" | PATH="$nojq" "$nojq/bash" "$redact")
    case "$out" in *withheld*) ok "no jq: withholds $t" ;; *) bad "no jq: passed $t" ;; esac
  done
  out=$(printf '%s' '{"tool_name":"mcp__epiphan__get_cms_events_for_devices","tool_response":{"title":"Keynote: Passwords 101"}}' | PATH="$nojq" "$nojq/bash" "$redact")
  if [ -z "$out" ]; then ok "no jq: ordinary text passes"; else bad "no jq: withheld ordinary text"; fi
else
  echo "skip no-jq checks (can't run a copied bash here, e.g. Git Bash on Windows)"
fi
rm -rf "$nojq"
# Shared corpus: tests/redaction-cases.json is byte-identical in Fleetwatch (src/fleetwatch/redact.py). Each input
# goes through the redactor as an MCP text block; none of must_not_contain may survive, every must_contain must,
# and redacting the result again must change nothing.
scrub() { # scrub <JSON string>: prints, as a JSON string, the text Claude would see after the redactor
  local out
  out=$(jq -cn --argjson t "$1" '{tool_name:"mcp__epiphan__get_stream_endpoints",tool_response:[{type:"text",text:$t}]}' | bash "$redact") || return 1
  if [ -z "$out" ]; then printf '%s' "$1"; else printf '%s' "$out" | jq -c '.hookSpecificOutput.updatedToolOutput[0].text' | tr -d '\r'; fi
}
n=$(jq '.cases | length' tests/redaction-cases.json | tr -d '\r')
i=0
while [ "$i" -lt "$n" ]; do
  c=$(jq -c --argjson i "$i" '.cases[$i]' tests/redaction-cases.json | tr -d '\r')
  id=$(printf '%s' "$c" | jq -r .id | tr -d '\r')
  once=$(scrub "$(printf '%s' "$c" | jq -c .input | tr -d '\r')")
  twice=$(scrub "$once")
  why=$(jq -nr --argjson c "$c" --argjson o "$once" '
    [($c.must_not_contain[] | select(. as $s | $o | contains($s)) | "leaks \(.)"),
     (($c.must_contain // [])[] | select(. as $s | $o | contains($s) | not) | "lost \(.)")] | join(", ")' | tr -d '\r')
  [ "$once" = "$twice" ] || why="${why:+$why, }not idempotent (second pass gave: $twice)"
  if [ -z "$why" ]; then ok "corpus $id"; else bad "corpus $id: $why (got: $once)"; fi
  i=$((i + 1))
done
if [ "$i" -gt 0 ]; then ok "corpus: $i cases run"; else bad "corpus: no cases"; fi
# More typed-mask and false-positive checks the corpus doesn't hold.
redacts "a mask inside https userinfo" 'https://u:[redacted]FAKE24@host.example/x'
redacts "a mask inside ftp userinfo"   'ftp://u:[redacted]FAKE25@files.example/x'
redacts "a mask before a Bearer token" 'Authorization: Bearer [redacted]FAKE26'
redacts "single-quoted value with space" "{'password': 'FAKE pw27'}"
redacts "a mask before https userinfo" 'https://[redacted]u:FAKE29@host.example/x'
redacts "a mask before rtmp userinfo"  'rtmp://[redacted]u:FAKE30@host.example/app'
redacts "a mask before wss userinfo"   'wss://[redacted]u:FAKE31@ws.example/x'
redacts "key=value"                    'key=FAKE32'
redacts "short Bearer token with a digit" 'Bearer FAKE3'
redacts "long Bearer token, letters only" 'Bearer FAKEabcdefghijklmnopqrstuvwxyz'
redacts "a bare Anthropic key"         'Anthropic said 401 for sk-ant-api03-FAKE34_abc-DEF'
redacts "an Anthropic key in brackets" 'request failed (sk-ant-api03-FAKE35).'
redacts "a mask before an Anthropic key" '[redacted]sk-ant-api03-FAKE36'
redacts "table stream-id column, not a UUID" "$(printf '| Name | Stream ID |\n|---|---|\n| YT | live/FAKE33 |')"
out=$(jq -cn --arg t "$(printf '| Name | Stream ID |\n|---|---|\n| YT | 0be33e88-d0f3-4421-8f26-f06c9092183c |')" \
  '{tool_name:"mcp__epiphan__get_stream_endpoints",tool_response:[{type:"text",text:$t}]}' | bash "$redact")
if [ -z "$out" ]; then ok "keeps a UUID in a table stream-id column"; else bad "masked a UUID stream ID in a table: $out"; fi
# Words that contain "key" aren't a key, and Bearer/Basic need a token-like value.
for t in 'monkey: banana' 'keyboard: US' 'hotkey: F5' 'Keynote: Passwords 101' 'monkey=banana' 'keyboard=US' 'hotkey=F5' 'Keynote=Passwords' \
         'Basic setup is done' 'Basic settings' 'Bearer of good news' 'a Bearer token' 'risk-ant-42 is a part number'; do
  t=$(jq -cn --arg t "$t" '$t' | tr -d '\r')
  once=$(scrub "$t")
  if [ "$once" = "$t" ]; then ok "leaves alone: $t"; else bad "changed plain text: $t -> $once"; fi
done
out=$(printf '%s' '{"tool_name":"mcp__epiphan__kb_publish","tool_response":{"stream_key":"FAKE"}}' | bash "$redact")
if [ -n "$out" ] && ! printf '%s' "$out" | grep -q FAKE; then ok "a new kb_ tool is still redacted"; else bad "a new kb_ tool skipped redaction"; fi

# Both hooks know the same Epiphan tools as settings.json.
known=$(jq -r '.permissions.allow[], .permissions.ask[] | select(startswith("mcp__epiphan__")) | sub("mcp__epiphan__"; "")' .claude/settings.json | tr -d '\r' | sort | tr '\n' ' ')
guard_known=$(grep -E '^(READS|WRITES)=' "$hook" | cut -d'"' -f2 | tr ' ' '\n' | grep . | sort | tr '\n' ' ')
redact_known=$(grep -E '^KNOWN=' "$redact" | cut -d'"' -f2 | tr ' ' '\n' | grep . | sort | tr '\n' ' ')
if [ "$known" = "$guard_known" ] && [ "$known" = "$redact_known" ]; then ok "hooks know the same 35 tools as settings.json"
else bad "tool lists differ between settings.json and the hooks"; fi
# Fields the commands need must survive: /stream-room uses StreamID, names and lock state.
out=$(jq -cn '{tool_name:"mcp__epiphan__get_stream_endpoints",tool_response:[{type:"text",text:({streams:[{StreamID:"0be33e88-d0f3-4421-8f26-f06c9092183c",Name:"YouTube",LockByDevice:"190x",CurrentlyStreaming:false,RTMP:{StreamingKey:"FAKE",URL:"rtmp://a.example/live2"}}]}|tojson)}]}' | bash "$redact")
if printf '%s' "$out" | jq -e '.hookSpecificOutput.updatedToolOutput[0].text | fromjson | .streams[0] | .StreamID == "0be33e88-d0f3-4421-8f26-f06c9092183c" and .Name == "YouTube" and .LockByDevice == "190x" and .RTMP.URL == "rtmp://a.example/[redacted]"' >/dev/null 2>&1; then
  ok "keeps StreamID, Name and LockByDevice"
else bad "redaction damaged fields the commands need: $out"; fi
# Fail closed: output that looks secret but can't be checked in time is withheld, never passed through.
big=$(jq -cn '{tool_name:"mcp__epiphan__get_stream_endpoints",tool_response:[{type:"text",text:([range(20000)|{Name:"n\(.)",RTMP:{StreamingKey:"FAKE\(.)"}}]|tojson)}]}')
out=$(printf '%s' "$big" | EPIPHAN_REDACT_SECONDS=0 bash "$redact")
if printf '%s' "$out" | jq -e '.hookSpecificOutput.updatedToolOutput | type == "string" and test("withheld")' >/dev/null 2>&1; then
  ok "withholds output it can't redact in time"
else bad "no fail-closed on timeout: ${out:0:120}"; fi
start=$SECONDS; out=$(printf '%s' "$big" | bash "$redact")
if [ $((SECONDS - start)) -le 15 ] && [ -n "$out" ] && ! printf '%s' "$out" | grep -q FAKE; then ok "redacts a ~1 MB output in $((SECONDS - start)) s"
else bad "~1 MB output: $((SECONDS - start)) s, leaked or withheld"; fi

for t in '{"tool_name":"mcp__epiphan__get_team_presets","tool_response":{"presets":[{"name":"x","StreamingKey":""}]}}' \
         '{"tool_name":"mcp__epiphan__kb_fetch","tool_response":"rtmp://a.example/live2 and a password"}' \
         'not json' ''; do
  out=$(printf '%s' "$t" | bash "$redact"); code=$?
  if [ "$code" -eq 0 ] && [ -z "$out" ]; then ok "redactor leaves alone: ${t:0:50}"; else bad "redactor changed: $t -> $out"; fi
done

# Bypass mode (which skips "ask") stays off in this folder.
if [ "$(jq -r '.permissions.disableBypassPermissionsMode' .claude/settings.json | tr -d '\r')" = disable ]; then ok "bypass mode disabled in settings"
else bad "settings.json no longer disables bypass mode"; fi
# The settings must ask (not allow) every write. Rule prefixes: two literal server names, and a glob for any
# "... Epiphan Cloud" connector (Claude Code accepts globs in ask/deny rules, not in allow rules).
rule_prefixes=(epiphan claude_ai_Epiphan_MCP 'claude_ai_*Epiphan_Cloud')
for p in "${rule_prefixes[@]}"; do
  n=$(jq --arg p "mcp__${p}__" '[.permissions.ask[] | select(startswith($p))] | length' .claude/settings.json)
  if [ "$n" -eq 15 ]; then ok "settings ask has 15 writes for $p"; else bad "settings ask has $n writes for $p"; fi
done
for p in epiphan claude_ai_Epiphan_MCP; do
  n=$(jq --arg p "mcp__${p}__" '[.permissions.allow[] | select(startswith($p))] | length' .claude/settings.json)
  if [ "$n" -eq 20 ]; then ok "settings allow has 20 reads for $p"; else bad "settings allow has $n reads for $p"; fi
done
n=$(jq '[.permissions.allow[] | select(startswith("mcp__") and contains("*"))] | length' .claude/settings.json)
if [ "$n" -eq 0 ]; then ok "no wildcard in mcp allow rules"; else bad "$n wildcard mcp rules in allow"; fi
n=$(jq '[.permissions.allow[], .permissions.ask[] | select(startswith("mcp__") and (startswith("mcp__epiphan__") or startswith("mcp__claude_ai_Epiphan_MCP__") or startswith("mcp__claude_ai_*Epiphan_Cloud__") | not))] | length' .claude/settings.json)
if [ "$n" -eq 0 ]; then ok "settings name no other connector"; else bad "$n settings rules name another connector"; fi
# The glob rules match every "... Epiphan Cloud" connector name (glob * read as the regex .*).
for c in claude_ai_Epiphan_Cloud claude_ai_TEST_Epiphan_Cloud claude_ai_Lab_Epiphan_Cloud; do
  n=$(jq --arg t "mcp__${c}__batch_reboot" '[.permissions.ask[] | select(contains("*")) | gsub("\\*"; ".*") | ("^" + . + "$") as $r | select($t | test($r))] | length' .claude/settings.json)
  if [ "$n" -eq 1 ]; then ok "an ask rule matches mcp__${c}__batch_reboot"; else bad "$n ask rules match mcp__${c}__batch_reboot"; fi
done
nonread=$(jq '[.permissions.allow[] | select(startswith("mcp__")) | select(test("__(get_|kb_)") | not)] | length' .claude/settings.json)
if [ "$nonread" -eq 0 ]; then ok "mcp allow list is reads only"; else bad "$nonread non-read tools in allow"; fi
n=$(jq '[.permissions.allow[] | select(startswith("Bash(uv run:") or startswith("Bash(uv run python") or . == "Bash(*)")] | length' .claude/settings.json)
if [ "$n" -eq 0 ]; then ok "no open-ended uv run or Bash rule in allow"; else bad "$n open-ended Bash rules in allow"; fi

# Both hooks use the same matcher: any server or connector with "epiphan" in its name, any case, any characters.
# Claude Code evaluates it as a JavaScript regex; jq's Oniguroma engine below supports the same syntax (character
# classes and a negative lookahead), so these checks hold for both.
matcher=$(jq -r '.hooks.PreToolUse[0].matcher' .claude/settings.json | tr -d '\r')
post=$(jq -r '.hooks.PostToolUse[0].matcher' .claude/settings.json | tr -d '\r')
if [ "$matcher" = "$post" ]; then ok "PreToolUse and PostToolUse matchers agree"; else bad "PreToolUse and PostToolUse matchers differ"; fi
for n in epiphan Epiphan epiphan-eu epiphan_eu plugin_av_epiphan claude_ai_Epiphan claude_ai_Epiphan_MCP claude_ai_epiphan_mcp \
         claude_ai_EPIPHAN_MCP claude_ai_Epiphan_Cloud claude_ai_EpiphanCloud claude_ai_Epiphan-Cloud claude_ai_My_Epiphan_Cloud \
         claude_ai_Epiphan_Edge claude_ai_Epiphan_Cloud_EU claude_ai_Epiphan_Pearl claude_ai_TEST_Epiphan_Cloud \
         claude_ai_Lab_Epiphan_Cloud epiphan.eu 'claude_ai_Epiphan_Cloud_(EU)' 'claude_ai_Epiphan Cloud'; do
  if jq -en --arg n "mcp__${n}__batch_reboot" --arg m "$matcher" '$n | test($m)' >/dev/null; then ok "matcher guards $n"; else bad "matcher misses $n"; fi
done
for n in claude_ai_Gmail__search claude_ai_Slack__send claude_ai_Gmail__search_epiphan_threads; do
  if jq -en --arg n "mcp__${n}" --arg m "$matcher" '$n | test($m)' >/dev/null; then bad "matcher wrongly guards mcp__$n"; else ok "matcher ignores mcp__$n"; fi
done

# check-secrets.sh (PreToolUse on file writes): every string in tool_input is checked; unreadable input is denied.
secrets=.claude/hooks/check-secrets.sh
secret_expect() { # secret_expect <deny|pass> <label> <tool_input JSON>
  local out code
  out=$(jq -cn --argjson ti "$3" '{hook_event_name:"PreToolUse",tool_name:"Write",tool_input:$ti}' | bash "$secrets"); code=$?
  if [ "$1" = pass ]; then
    [ "$code" -eq 0 ] && [ -z "$out" ] && { ok "secrets pass  $2"; return; }
  else
    [ "$code" -eq 0 ] && printf '%s' "$out" | jq -e '.hookSpecificOutput.hookEventName == "PreToolUse" and .hookSpecificOutput.permissionDecision == "deny"' >/dev/null 2>&1 \
      && { ok "secrets deny  $2"; return; }
  fi
  bad "secrets $1 $2 (exit=$code, out=$out)"
}
# Fake values are built from pieces so this file never holds a whole one.
gh="ghp_$(printf 'a%.0s' {1..36})"
aws="AKIA""ABCDEFGHIJKLMNOP"
pem="-----BEGIN ""RSA PRIVATE KEY-----"
ant="sk-ant-""api03-$(printf 'b%.0s' {1..24})"
secret_expect deny "GitHub token in Write content"   "$(jq -cn --arg c "token = \"$gh\"" '{file_path:"x.py",content:$c}')"
secret_expect deny "AWS key in Edit new_string"      "$(jq -cn --arg c "$aws" '{file_path:"x.py",old_string:"a",new_string:$c}')"
secret_expect deny "private key (leading dashes)"    "$(jq -cn --arg c "$pem" '{file_path:"k.txt",content:$c}')"
secret_expect deny "Anthropic key in MultiEdit"      "$(jq -cn --arg c "$ant" '{file_path:"x.py",edits:[{old_string:"a",new_string:$c}]}')"
secret_expect deny "Pearl password in an env file"   '{"file_path":".env","content":"PEARL_HOST=10.0.0.5\nPEARL_PASSWORD=hunter2\n"}'
secret_expect pass "empty Pearl password"            '{"file_path":".env.example","content":"PEARL_HOST=192.168.1.50\nPEARL_PASSWORD=\nPEARL_VERIFY_TLS=true\n"}'
secret_expect pass "ordinary code"                   '{"file_path":"x.py","content":"password: SecretStr = SecretStr(\"\")\nkey = sha256_of(path)\n"}'
for t in '' 'not json'; do
  out=$(printf '%s' "$t" | bash "$secrets")
  if printf '%s' "$out" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null 2>&1; then ok "secrets deny unreadable input: '${t}'"
  else bad "secrets let unreadable input through: '${t}' -> $out"; fi
done
matcher=$(jq -r '.hooks.PreToolUse[1].matcher' .claude/settings.json | tr -d '\r')
for t in Write Edit MultiEdit NotebookEdit; do
  if jq -en --arg n "$t" --arg m "$matcher" '$n | test($m)' >/dev/null; then ok "check-secrets runs on $t"; else bad "check-secrets misses $t"; fi
done
if jq -en --arg m "$matcher" '"Read" | test($m)' >/dev/null; then bad "check-secrets runs on Read"; else ok "check-secrets skips Read"; fi
if [ "$fails" -ne 0 ]; then echo "$fails failed."; exit 1; fi
echo "All hook tests passed."

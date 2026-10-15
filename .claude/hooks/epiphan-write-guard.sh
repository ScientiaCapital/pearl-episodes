#!/usr/bin/env bash
# PreToolUse guard for the Epiphan MCP server and claude.ai connectors to it. The matcher in
# .claude/settings.json sends every server with "epiphan" in its name here; this decides which calls matter:
#   - the Epiphan Edge tools this kit knows: reads pass, writes need your approval;
#   - any other tool on the device server itself (the kit's "epiphan" server, or a connector named like
#     "Epiphan MCP" / "Epiphan Cloud" / "Test Epiphan Cloud" / "Epiphan Edge") needs approval, even one named like
#     a read (get_*, kb_*), so tools the server adds later are covered;
#   - other Epiphan services (a connector for docs, CRM, ...) are left to Claude Code's normal permissions.
# Disruptive writes (reboot, firmware, stop, delete, presets) get a louder warning in the approval prompt.
# In bypass mode Claude Code skips "ask", so writes are denied there instead ("deny" still applies).
# With EPIPHAN_READ_ONLY set to anything but empty, 0, false, no or off (spaces and case ignored), every one of
# those calls is denied instead of asked.
# Fails closed: a call it can't read (no tool_name, or one that isn't a string) is denied, never waved through,
# and a tool name with a character outside [A-Za-z0-9_-] is never taken for a read.
# jq is used when present; otherwise grep, which works on a stock Mac and in Git Bash on Windows.
# Keep these lists in step with .claude/settings.json and epiphan-redact.sh (tests/hook-test.sh checks).
READS=" get_devices_in_my_team get_device_info get_device_sources get_system_status_for_devices get_recorder_status_for_devices get_storage_status_for_devices get_channel_settings get_channel_image get_channel_audio_levels get_stream_endpoint get_stream_endpoints get_team_presets get_cms_events_for_device get_cms_events_for_devices get_current_or_next_cms_event_for_device get_current_or_next_cms_events_for_devices get_cms_names_for_devices get_devices_by_cms kb_search kb_fetch "
WRITES=" batch_recording start_stream_endpoint stop_stream_endpoint create_cms_event update_cms_event delete_cms_event cms_event_action confirm_cms_event_on_device create_stream_endpoint update_stream_endpoint delete_stream_endpoint apply_team_preset switch_device_to_cms batch_reboot batch_firmware_update "
DEVICE_SERVER='^(epiphan([-_].*)?|claude_ai_(.*_)?epiphan([-_]?(mcp|cloud|edge)([-_].*)?)?|plugin_.*epiphan.*)$'
input=$(cat)
unsure=""

if command -v jq >/dev/null 2>&1 && parsed=$(printf '%s' "$input" | jq -r '[(.tool_name | if type == "string" then . else "" end), (.permission_mode // "" | tostring)] | map(gsub("\n"; " ")) | join("\n")' 2>/dev/null); then
  name=${parsed%%$'\n'*}
  mode=${parsed#*$'\n'}
else
  field() { printf '%s' "$input" | grep -o "\"$1\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" | head -1 | sed 's/.*"\([^"]*\)"$/\1/'; }
  name=$(field tool_name)
  mode=$(field permission_mode)
  # Without a real parser, don't let a nested copy of a field decide: a second "tool_name" means the call
  # can't be trusted to be a read, and bypass mode anywhere in the input counts as bypass mode.
  if [ "$(printf '%s' "$input" | grep -o '"tool_name"' | wc -l)" -gt 1 ]; then unsure=1; fi
  if printf '%s' "$input" | grep -q '"permission_mode"[[:space:]]*:[[:space:]]*"bypassPermissions"'; then mode=bypassPermissions; fi
fi
name=${name//$'\r'/}; mode=${mode//$'\r'/}         # jq on Windows ends lines with CRLF
server=${name%__*}; server=${server#mcp__}
raw=${name##*__}                                    # strip the server prefix (mcp__epiphan__, mcp__claude_ai_Epiphan_MCP__, ...)
tool=$(printf '%s' "$raw" | tr -cd 'A-Za-z0-9_-')   # it goes into JSON below; keep it to safe characters

decide() { # decide <ask|deny> <reason>
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"%s","permissionDecisionReason":"%s"}}\n' "$1" "$2"
  exit 0
}
read_only() { # on unless EPIPHAN_READ_ONLY is empty, 0, false, no or off (spaces and case ignored)
  case "$(printf '%s' "${EPIPHAN_READ_ONLY:-}" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')" in ''|0|false|no|off) return 1 ;; esac
  return 0
}
write() {
  if read_only; then
    decide deny "READ-ONLY: '${tool:-unknown}' changes Epiphan devices, and this Claude Code session was started in read-only mode (EPIPHAN_READ_ONLY), so it's blocked. To make changes, with your approval each time, type /exit and start claude again without EPIPHAN_READ_ONLY."
  fi
  if [ "$mode" = bypassPermissions ]; then
    decide deny "BLOCKED: '${tool:-unknown}' changes Epiphan devices, and bypass mode would run it without asking. Leave bypass mode (Shift+Tab) and try again to approve it yourself."
  fi
  case "$tool" in
    batch_reboot|batch_firmware_update)
      decide ask "DISRUPTIVE: '$tool' takes devices offline and interrupts any live recording or stream. Check the device list in the call." ;;
    stop_*|delete_*)
      decide ask "DISRUPTIVE: '$tool' stops or removes something that may be live or scheduled. Check the target before approving." ;;
    apply_team_preset)
      decide ask "DISRUPTIVE: 'apply_team_preset' overwrites device settings. Presets with network or system sections can cut the device off or reset its password." ;;
    switch_device_to_cms|update_cms_event|cms_event_action)
      decide ask "DISRUPTIVE: '$tool' changes a scheduled event or which platform the device records for, so a class may record or stream differently than planned. Check the device and the event before approving." ;;
    *)
      decide ask "WRITE: '$tool' changes a setting or starts an action on your Epiphan Edge devices." ;;
  esac
}

[ -n "$tool" ] || decide deny "BLOCKED: couldn't read this Epiphan tool call, so it isn't allowed to run. Try again."
[ -n "$unsure" ] && write
[ "$raw" = "$tool" ] || write                      # a name with an odd character in it isn't one of the reads
case "$READS" in *" $tool "*) exit 0 ;; esac
case "$WRITES" in *" $tool "*) write ;; esac
# Anything else on the device server asks, even a new tool named like a read: only the list above is trusted.
printf '%s' "$server" | grep -qiE "$DEVICE_SERVER" && write
exit 0  # another Epiphan service (docs, CRM, ...): Claude Code's normal permissions apply

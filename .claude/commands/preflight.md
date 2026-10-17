---
description: Read-only preflight for the channels you name, using the Epiphan Edge read tools
argument-hint: <device_id>-<channel_id> [...]
allowed-tools: Bash, Read, Write, mcp__epiphan__get_devices_in_my_team, mcp__epiphan__get_storage_status_for_devices, mcp__epiphan__get_channel_settings, mcp__claude_ai_Epiphan_MCP__get_devices_in_my_team, mcp__claude_ai_Epiphan_MCP__get_storage_status_for_devices, mcp__claude_ai_Epiphan_MCP__get_channel_settings
---

Check whether these channels can start a take: $ARGUMENTS

Each argument is a channel address, `<device_id>-<channel_id>`. If none were given, call `get_devices_in_my_team`,
list the online devices and channels, and ask which to check. Do not guess.

**Read tools only.** Never call `batch_recording`, a preset, event, stream, reboot or firmware tool from this
command. If the Edge team looks like Epiphan's shared demo fleet, say so before going on, and do not write its
device, room or group names anywhere in the repo.

1. `get_devices_in_my_team` (all devices, no filter).
2. `get_storage_status_for_devices` for the device ids in the arguments.
3. `get_channel_settings` for each channel in the arguments.
4. Write one JSON file in the session scratchpad, never in the repo, shaped like this:
   `{"devices": <the "devices" list>, "storage": <the "storage" list>, "channel_settings": {"<address>": <the "settings" list>}}`
5. Run `uv run pearl-episodes preflight <that file> --channel <address> ...` (repeat `--channel`) and show the
   output as printed. `--min-free-bytes` changes the storage floor.

Report each channel as OK or NOT READY, name the failed checks, and keep `UNVERIFIED` lines visible: they mark what
the kb does not settle. Describe nothing about timing or alignment between cameras or devices. Delete the scratch
file when you are done; it names devices.

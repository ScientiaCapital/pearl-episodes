# Epiphan safety

- The 20 Epiphan Edge read tools are allowed. Every write (`batch_recording`, stream endpoints, CMS events,
  presets, `switch_device_to_cms`, `batch_reboot`, `batch_firmware_update`) asks first and names the device,
  channel and expected effect. Reboot and firmware update interrupt live recordings and streams. Enforced by
  `permissions.ask`, bypass mode off, and `.claude/hooks/epiphan-write-guard.sh` (from the Epiphan Edge Claude
  Kit), which also asks for any unknown tool on the Edge server. `EPIPHAN_READ_ONLY=1 claude` blocks writes.
- Never the DEV or STAGING connectors. Never `Epiphan_Ai` (customer data) from this project.
- Develop and record on Tim's own bench devices (`docs/HARDWARE.md`). The Edge team sometimes visible is
  Epiphan's shared demo fleet. Record on it only in a session where Tim says so, prefer a six-channel Pearl-2,
  and check free storage first (`get_storage_status_for_devices`): a full disk overwrites the oldest files. Never
  write its device, room or group names into this repo.
- Mask stream keys, passwords and credentialed RTMP/SRT URLs (`rtmp://host/app/[redacted]`). The PostToolUse
  hook `.claude/hooks/epiphan-redact.sh` (from the Kit, needs `jq`) does this for every Epiphan tool result and
  withholds output it can't check. Keep both hooks registered and byte-identical with the Kit; `bash
  tests/hook-test.sh` checks them against the redaction cases shared with Fleetwatch.
- Preview frames may show people. Describe them by role and state only.
- No claim about timing or alignment across cameras or devices, in code, comments, docs or chat.

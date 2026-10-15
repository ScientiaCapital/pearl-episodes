# Epiphan safety

- Read tools (`get_*`, `kb_*`) are allowed. Every write on Epiphan Edge (`batch_recording`, stream endpoints,
  CMS events, presets, `switch_device_to_cms`, `batch_reboot`, `batch_firmware_update`) asks first and names the
  device, channel and expected effect. Reboot and firmware update interrupt live recordings and streams.
- Never the DEV or STAGING connectors. Never `Epiphan_Ai` (customer data) from this project.
- The visible team is Epiphan's demo fleet, shared with the sales team. Record on it only in a session where Tim
  says so. Prefer Broadcast Studio or Council Chamber (Pearl-2, six channels). Check free storage first: two
  Pearl-2 units were at about 1.3 GB free on 2026-10-14, and a full disk overwrites the oldest files.
- Mask stream keys, passwords and credentialed RTMP/SRT URLs (`rtmp://host/app/••••`). The PostToolUse hook
  `.claude/hooks/epiphan-redact.py` does this for MCP results; keep it registered.
- Preview frames may show people. Describe them by role and state only.
- No claim about timing or alignment across cameras or devices, in code, comments, docs or chat.

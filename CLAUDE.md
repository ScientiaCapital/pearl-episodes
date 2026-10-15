# pearl-episodes

Record robot-learning demonstrations on Epiphan Pearl, run the stations through Epiphan Edge, and package each
take as an episode in the formats labs use (LeRobot, RLDS). This is Tim's build-and-learn project behind the
Physical AI lab proof of concept. Read `.claude/PROJECT_CONTEXT.md` at session start and `docs/ARCHITECTURE.md`
before touching code.

## Context documents (read before building anything new)
`docs/context/README.md` links the four Epiphan documents and the pro forma on Google Drive. They explain the
market, the proof of concept and the measures this code has to produce. The files themselves are never committed.

## Epiphan tools
- Fleet: the `epiphan` MCP server in `.mcp.json` (tools `mcp__epiphan__*`) or the claude.ai "Epiphan MCP"
  connector (`mcp__claude_ai_Epiphan_MCP__*`). Never DEV or STAGING connectors. Read tools are allowed; every
  write (`batch_recording`, presets, events, reboot, firmware) asks first and names the device and channel.
- Product facts: the Epiphan Knowledge connector or `kb_search`/`kb_fetch`. Never from memory. If a page does
  not cover it, say so.
- Development hardware is Tim's own Pearl Mini, EC20 and (soon) Nano (`docs/HARDWARE.md`). Use those first.
- The Edge team visible in some sessions is Epiphan's own demo fleet. Treat it as shared: record on it only when Tim says so in the session, never during business hours
  without asking, and never change presets, events or firmware.

## Rules that are not negotiable
1. **No claim about multi-camera alignment, timing or sync.** Record `clock_source` and leave it there.
2. **No OpenAI.** Anthropic direct, or DeepSeek/Qwen/Groq via OpenRouter, if a model is ever needed.
3. **Python 3.12+, async for all I/O, type hints on every function.** `uv` for everything. `ruff` clean.
4. **Secrets stay in `.env`.** Mask stream keys and credentialed URLs in any output. Recordings and episodes are
   gitignored and may contain people; they stay on this machine unless the lab says otherwise.
5. **Pearl REST API: use only what Epiphan's OpenAPI spec and the kb.epiphan.com pages say** (verified
   2026-10-14, see `docs/ARCHITECTURE.md`). Do not invent endpoints, fields, ports or firmware behaviour.
   Re-verify on a real device before trusting timing, error cases or anything the spec leaves open.
6. Internal Epiphan documents and customer data never go into this repository.

## Data model
Team → Devices (`Id`) → Channels (`channel_id`) → recording_status, publishers. Batch channel address is
`<device_id>-<channel_id>`. Edge-controlled recordings are MP4 with a 500 MB cap; files roll every 30 minutes or
500 MB, so one take can be several files.

## Workflow
`/begin` loads context, `/status` checks state, `/build` for features, `/ship` to commit and push, `/end` to
close the day (observers, secrets sweep, context sync). Tasks live in `.claude/TASK.md`, the queue in
`.claude/BACKLOG.md`.

# pearl-episodes

@AGENTS.md

AGENTS.md (imported above) has the commands, hard rules, style and map for any assistant. This file adds what
Claude Code needs. This is Tim's build-and-learn project behind the Physical AI lab proof of concept. Read
`.claude/PROJECT_CONTEXT.md` at session start and `docs/ARCHITECTURE.md` before touching code.

## Context documents (read before building anything new)
`docs/context/README.md` links the four Epiphan documents and the pro forma on Google Drive. They explain the
market, the proof of concept and the measures this code has to produce. The files themselves are never committed.

## Epiphan tools
- Fleet: the `epiphan` MCP server in `.mcp.json` (tools `mcp__epiphan__*`) or the claude.ai "Epiphan MCP"
  connector (`mcp__claude_ai_Epiphan_MCP__*`). Never DEV or STAGING connectors, never `Epiphan_Ai` (denied in
  `.claude/settings.json`). Read tools are allowed; every write (`batch_recording`, presets, events, reboot,
  firmware) asks first and names the device and channel. Rules in `.claude/rules/epiphan-safety.md`.
- Product facts: the Epiphan Knowledge connector or `kb_search`/`kb_fetch`. Never from memory. If a page does
  not cover it, say so.
- Development hardware is Tim's own Pearl Mini (the PoC station), EC20 and (soon) Nano (`docs/HARDWARE.md`).
  Use those first.
- The Edge team visible in some sessions is Epiphan's shared demo fleet. Treat it as shared: record on it only
  when Tim says so in the session, never during business hours without asking, and never change presets, events
  or firmware. Don't write its device, room or group names into this repo.

## Data model
Team → Devices (`Id`) → Channels (`channel_id`) → recording_status, publishers. Batch channel address is
`<device_id>-<channel_id>`. Pearl rolls a recording into a new file at 30 minutes or 500 MB by default, so one
take can be several files; a channel controlled by Edge must record MP4 with a 500 MB maximum file size.

## Gotchas
- The hooks need `jq`. Without it `check-secrets.sh` denies every file write and the redactor withholds output.
- A test that needs a fake secret builds it from pieces (see `tests/hook-test.sh`), or `check-secrets.sh` denies
  the write. `tests/redaction-cases.json` is allowlisted in `.gitleaks.toml` and stays byte-identical with the Edge
  Claude Kit and Fleetwatch; change it there first.
- `docs/assets/epiphan-logo*.svg` are byte-identical Brand MCP assets (re-fetch from the asset URL, never edit).
  Banners and the architecture diagram are generated: `python3 scripts/build_readme_art.py`.
- Shared prose (README, anything that leaves the repo) uses US spelling and passes the Epiphan Brand
  `check_my_copy`. Product facts still come from the kb.
- `main` has no branch protection on this plan. Branch and PR; merging, force-pushing or rewriting history needs
  Tim's OK in that session. History was scrubbed of internal content on 2026-10-14; don't reintroduce it.

## Workflow
`/begin` loads context, `/status` checks state, `/build` for features, `/ship` to commit and push, `/end` to
close the day (observers, secrets sweep, context sync). Tasks live in `.claude/TASK.md`, the queue in
`.claude/BACKLOG.md`, the design in `.claude/PLAN.md`.

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

## Pipeline (CLI)
`pull <recorder_id>` puts new files in `recordings/<host>/<recorder_id>/` with an `index.jsonl`. `package --camera
...` builds `episodes/<id>/` (`source/`, `joined/`, `manifest.json`, `hashes.txt`) by remux, never a re-encode.
`export <episode_dir>` adds `lerobot/` (v3.0). Existing episodes and exports are never overwritten. Segments are
ordered by the device's raw `created` text, then file id; never parse file names or times.
`preflight <json> --channel <device_id>-<channel_id>` checks channels from saved Edge read-tool output (devices,
storage, channel settings). Python cannot call MCP tools, so `/preflight` has a Claude session gather the JSON
into the scratchpad (never the repo), run the command, and delete the file. It is read only; a check the kb does
not settle is `UNVERIFIED`, not a failure.

## Gotchas
- `ffmpeg` and `ffprobe` must be installed. Tests that need them skip without them; CI installs them.
- CI syncs with `--frozen`: after changing dependencies in `pyproject.toml`, run `uv lock` and commit it.
- Notebooks are committed with outputs cleared (pre-commit hook `notebook-outputs-cleared`), because frames can
  show people. Run them from a scratch copy and keep executed copies outside the repo.
- CI skips `tests/test_lerobot_loader.py` (needs the `datasets` extra). After any lerobot change, run it in a
  scratch venv outside the repo:
  `uv venv <dir> --python 3.12 && uv pip install --python <dir>/bin/python "lerobot[dataset,av-dep]==0.6.1" pytest pytest-asyncio httpx pydantic pydantic-settings anyio`,
  then `PYTHONPATH=src <dir>/bin/python -m pytest -m datasets tests/test_lerobot_loader.py`.
- `torchcodec` (LeRobot's default decoder) supports FFmpeg 4 to 8. With FFmpeg 9 installed LeRobot falls back to
  `pyav`, and `StreamingLeRobotDataset` (torchcodec only in 0.6.1) cannot run. Tests and the notebook use `pyav`.
- Run the gate with `&&` so a failure stops the commit: ruff check and format, pytest, `bash tests/hook-test.sh`,
  `uvx pre-commit run --all-files`. A PR's Evidence section comes from the final commit.
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
close the day (observers, secrets sweep, context sync), `/preflight` to check channels before a take (read only). Tasks live in `.claude/TASK.md`, the queue in
`.claude/BACKLOG.md`, the design in `.claude/PLAN.md`.

# pearl-episodes

Record robot-learning demonstrations on **Epiphan Pearl**, run the stations from one screen through **Epiphan Edge**, and package every take as an episode in the formats labs already use (**LeRobot**, **RLDS** as used by Open X-Embodiment).

Why: 38 of the 72 datasets in the Open X-Embodiment collection were recorded by a person at a fixed station with one to four exterior cameras. That station runs USB cameras into a workstation with software encoding, keeps one copy, and carries no per-take context once the video leaves the lab's own tooling. A dedicated recorder beside it, plus a fleet layer to run many stations, is what this project tests.

## What it does (target)

1. **Operate.** Claude Code drives Epiphan Edge over MCP: pick a group of Pearl devices, start and stop recording across them, snapshot each channel, watch storage.
2. **Pull and package.** Per device, list recordings through the Pearl REST API, download them, hash each file (SHA-256), and write one episode: one video per camera, a step table with timestamps, and a manifest (device serial, channel, firmware, start time, duration, task label, operator, clock source).
3. **Analyze.** Load the episodes with LeRobot, compare them with DROID and Bridge episodes, and run an Open X-Embodiment model in Colab or on RunPod against frames Pearl captured.

Stretch: if custom applications can be installed from Pearl's Apps page, an on-device agent that writes the manifest at record stop.

## Status

Bones only. `pearl-episodes doctor` runs; the Pearl client, packager and CLI are stubs with the shapes decided. See `docs/ARCHITECTURE.md` and `.claude/TASK.md`.

## Setup

```bash
uv sync --group dev          # core tooling
uv sync --extra datasets     # LeRobot, TensorFlow, TFDS (large; on purpose)
cp .env.example .env         # fill in one Pearl's host and admin password
uv run pearl-episodes doctor
```

Epiphan Edge is reached through the `epiphan` MCP server in `.mcp.json` (or the claude.ai "Epiphan MCP" connector). Write tools on Edge need an Edge Premium plan and are approval-gated in this workspace.

## Layout

```
src/pearl_episodes/
  config.py            settings from .env
  pearl/client.py      async Pearl REST client (list, download, bulk start/stop)
  episodes/manifest.py the episode manifest model
  episodes/packager.py hash + manifest + layout for LeRobot/RLDS
  cli.py               doctor | list | pull | package
docs/ARCHITECTURE.md   the design and the open product questions
docs/context/          links to the brief, one-pager, PoC design and pro forma (files themselves are not committed)
```

Apache-2.0. Internal Epiphan documents referenced here stay out of the repository.

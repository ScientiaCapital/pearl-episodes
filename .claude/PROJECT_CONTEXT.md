# pearl-episodes

**Branch**: main | **Updated**: 2026-10-14

## Status
Scaffolded 2026-10-14 from the `epiphan-mcp-agent` workspace template and the `fleetwatch` Python layout.
Bones only: settings, async Pearl REST client (list, download, bulk start/stop), episode manifest model with
SHA-256 hashing, packager stub, CLI (`doctor` works, `list` talks to a device, `pull` and `package` not built).
One test passes. GitHub: `ScientiaCapital/pearl-episodes` (private).

## Why this exists
The Physical AI lab proof of concept (see `docs/context/README.md`) needs one artifact above all: a Pearl
recording that drops into the dataset format a robotics lab already uses, with a manifest that carries what the
product does not (task, operator, clock source, hash). This project builds that, and lets Claude Code act as
the station operator through Epiphan Edge.

## Next session's focus
1. [ ] Read the four Drive documents and the pro forma (`docs/context/README.md`), then `docs/ARCHITECTURE.md`
2. [x] Pearl REST API checked against Epiphan's OpenAPI spec 2026-10-14 (base `/api/v2.0`, Basic auth). Still to
       do: first bench session on Tim's Pearl Mini + EC20 (`docs/HARDWARE.md`), confirm real responses
3. [ ] `pearl-episodes pull`: new recordings for a recorder to `recordings/<serial>/`, idempotent on file id
4. [ ] `pearl-episodes package`: one episode directory per take, stitch rolled segments, write manifest + hashes
5. [ ] LeRobot layout writer and a notebook that loads one packaged episode beside a DROID episode
6. [ ] Operator session script: Edge MCP start, wait, stop, then pull and package; log every warning seen

## Product input
- 2026-10-14, Yusupha (Slack): Docker "will be fine running on Nano", with some effort to upgrade the Linux kernel.
  Expectation only; not a commitment. Makes the on-device manifest agent plausible on the Nano bench unit.

## Decisions
- Independent recording beside the lab rig is the default; same-feed only where cameras output HDMI/SDI/IP.
- `clock_source` is recorded, never interpreted. No timing claims.
- Heavy ML dependencies are an optional extra (`uv sync --extra datasets`), unpinned until first verified
  install on Apple silicon.

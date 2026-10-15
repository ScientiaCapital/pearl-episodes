# pearl-episodes

**Branch**: main | **Updated**: 2026-10-14

## Status
Early. `doctor` and `list <recorder_id>` work against one Pearl. The async REST client covers recorders, archive
listing, download and bulk start/stop; the manifest model and SHA-256 hashing exist. `pull`, `package` and the
LeRobot/RLDS layouts are not built. Safety baseline in place (2026-10-14): the Edge Claude Kit's write guard and
redaction hooks, a working secrets hook, gitleaks, pinned CI. Private repo, Epiphan-owned.

## Why this exists
The Physical AI lab proof of concept (see `docs/context/README.md`) needs one artifact above all: a Pearl
recording that drops into the dataset format a robotics lab already uses, with a manifest that carries what the
product does not (task, operator, clock source, hash). DROID campuses that already run Pearl are the entry
(`.claude/PLAN.md` §7). This project builds that, and lets Claude Code act as the station operator through Edge.

## Next session's focus
1. [ ] Client hardening (`.claude/BACKLOG.md`, first item)
2. [ ] First bench session on the Pearl Mini PoC station (`docs/HARDWARE.md`): confirm real responses
3. [ ] `pearl-episodes pull`, then `package` with manifest v2
4. [ ] LeRobot export and the notebook beside a DROID episode
5. [ ] Bench codec test (H.264 bitrates vs LeRobot AV1)

## Product input
- 2026-10-14: Product expects containers on Pearl Nano are feasible with kernel work. Expectation only, not a
  commitment. Makes the on-device manifest agent plausible on the Nano bench unit.
- 2026-10-14: Pearl records H.264 (Nano also H.265), 4:2:0, 8-bit. For color video that matches what LeRobot
  stores (yuv420p); depth needs 12-bit lossless in LeRobot, so depth stays on the lab's own stack.

## Decisions
- Independent recording beside the lab rig is the default; the PoC station is a Pearl Mini with two EC20s on the
  DROID cart. The next Pearl is the intended production station; nothing depends on its specs.
- USB (UVC) input is documented on Pearl-2 and Mini, not Nano; which lab cameras work is a bench test.
- `clock_source` is recorded, never interpreted. No timing claims.
- Exports keep Pearl's H.264 as-is (remux, no re-encode).
- Heavy ML dependencies are an optional extra (`uv sync --extra datasets`), unpinned until first verified
  install on Apple silicon.
- Copyright Epiphan Systems Inc., all rights reserved (LICENSE, NOTICE).

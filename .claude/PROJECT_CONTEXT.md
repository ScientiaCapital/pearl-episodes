# pearl-episodes

**Branch**: main | **Updated**: 2026-10-16

## Status
Sprint 1 built (2026-10-15, PRs #16 to #24): the client checks the response envelope, downloads are atomic and
size-verified, recorder status and `recorders` exist, manifest v2, `pull`, `package` (remux, no re-encode), the
LeRobot v3.0 export (opens with lerobot 0.6.1's own loader), and the notebook beside a DROID episode. Nothing has
run against a real device yet: no `.env`, so all fixtures are hand-written or generated. RLDS export and the
start/stop part of the operator session script are not built. Added 2026-10-16 (PRs #29, #30): the read-only
`/preflight` (`pearl-episodes preflight`), and a re-check of the REST surface against the published spec and the kb,
with the kb page cited beside each client call (bookmarks take a required `text` query parameter; no REST call
returns the Date and Time protocol). Safety baseline in place (2026-10-14): the Edge Claude Kit's write guard and
redaction hooks, a working secrets hook, gitleaks, pinned CI. Private repo, Epiphan-owned.

## Why this exists
The Physical AI lab proof of concept (see `docs/context/README.md`) needs one artifact above all: a Pearl
recording that drops into the dataset format a robotics lab already uses, with a manifest that carries what the
product does not (task, operator, clock source, hash). DROID campuses that already run Pearl are the entry
(`.claude/PLAN.md` §7). This project builds that, and lets Claude Code act as the station operator through Edge.

## Next session's focus
Bench day (Tim, with the Pearl Mini): #10 first session and real fixtures, #11 codec test (`scripts/codec_compare.sh`), #12 USB cameras. #14 waits on Product's written answers. Then the operator session script, per-take labels and RLDS export (`.claude/BACKLOG.md`).

Next session: bench day #10 via `/preflight` then `batch_recording` (every write asks first) once the bench Mini is visible in Edge | Tim is travelling the week of 2026-10-19, so Sprint 1's 2026-10-22 date will likely move | Est: half a day | Observer notes: no real Pearl file has been through `pull`, `package` or `export`; check HTTPS on the device first (the client assumes it).

## 2026-10-14 close
Safety baseline merged (PR #1, CI green); README with brand banner and static diagram; history scrubbed of
internal content and force-pushed; PoC brief, at-a-glance and opportunity brief PDFs updated in Drive (same
links). Known leftover: GitHub keeps PR #1's original commits under a hidden ref until GitHub Support removes it.

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

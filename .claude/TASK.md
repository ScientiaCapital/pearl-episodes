# Current Task

**Sprint 1, 2026-10-15** (milestone due 2026-10-22; Tim is travelling the week of 2026-10-19, so expect it to slip
and move the date when the bench day is known):
https://github.com/ScientiaCapital/pearl-episodes/milestone/1

Goal: one real take from the Pearl Mini PoC station pulled, packaged with manifest v2 and hashes, exported to
LeRobot and opened beside a DROID episode.

Built (code, no device): #2, #3, #4, #5, #6, #7, #8, #9, #13 on 2026-10-15; and on 2026-10-16 the read-only
`/preflight` (#29), the REST re-check with a kb page beside each client call (#30), and the README, CLAUDE.md and
context update (#31). Everything runs on generated test patterns and mocked transports.

Left for Tim, needs the Mini on the bench and visible in Edge (until then, no writes; `/preflight` and fixtures only):
1. #10 first session: `cp .env.example .env`, check the device serves HTTPS (the client assumes it), `doctor`,
   `recorders`, `list`, then `/preflight` on the channels, one short take through `batch_recording` (asks first),
   `pull`, and capture redacted fixtures.
2. `package` and `export` on the first real take; run the notebook with `PEARL_LEROBOT` pointing at it. Note what
   the real `created` text looks like and whether the 30 min / 500 MB rollover remuxes cleanly.
3. #11 codec test (`scripts/codec_compare.sh`; H.264 bitrates against LeRobot's AV1 default; also the key frame
   interval question).
4. #12 USB cameras.
5. #14 send the open questions to Product (`.claude/PLAN.md` section 6, items 1 to 13) and record written answers.
6. While on the bench: does `POST /channels/{cid}/bookmarks` (`text` parameter) show in the file or archive
   listing, and does a `MP4 Fragmented` file type work under Edge control? Record both in `docs/ARCHITECTURE.md`.

Next sprint (Sprint 2), in this order once a real take exists (details and effort in `.claude/BACKLOG.md`):
operator session start and stop with a session log, per-take labels, RLDS export.

One issue per branch and PR, Conventional Commit title, CI green, Evidence in the PR template. Merging needs Tim's OK.

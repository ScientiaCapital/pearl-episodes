# Current Task

**Sprint 1, 2026-10-15** (milestone due 2026-10-22):
https://github.com/ScientiaCapital/pearl-episodes/milestone/1

Goal: one real take from the Pearl Mini PoC station pulled, packaged with manifest v2 and hashes, exported to
LeRobot and opened beside a DROID episode.

Built 2026-10-15 (code, no device): #2, #3, #4, #5, #6, #7, #8, #9, #13. Everything runs on generated test
patterns and mocked transports.

Left for Tim, needs the Mini on the bench:
1. #10 first session: `cp .env.example .env`, `doctor`, `recorders`, `list`, `pull`, then capture redacted fixtures.
2. `package` and `export` on the first real take; run the notebook with `PEARL_LEROBOT` pointing at it.
3. #11 codec test (H.264 bitrates against LeRobot's AV1 default; also the key frame interval question).
4. #12 USB cameras.
5. #14 send the open questions to Product (`.claude/PLAN.md` section 6, items 1 to 13) and record written answers.

One issue per branch and PR, Conventional Commit title, CI green, Evidence in the PR template.

# ARCH

Point-in-time audit, end of 2026-10-16. Format: `[LEVEL] — component — what — impact`.
Yesterday's report is in `.claude/archive/2026-10-15-OBSERVER-ARCH.md`; its open items carry over (below).

- [RISK] — Pearl REST over HTTPS — the client always uses `https://`; the kb says `http://` is the default and
  `https://` applies if HTTPS is configured on the device. A bench Pearl without HTTPS fails the first call —
  check the device's setting before `doctor` on bench day
- [RISK] — repository ownership — README and LICENSE state Epiphan Systems Inc. confidential, while the repo and
  the Edge Claude Kit and Fleetwatch links sit in a personal GitHub org — a decision for Tim and Epiphan IT, not
  made in code
- [RISK] — the visible Edge team looks like Epiphan's shared demo fleet and no bench Mini is identified; two
  Pearl-2 units report `disk_space_error` — no recording on the shared fleet unless Tim says so in that session
- [SMELL] — operator session — preflight is built; start/stop through `batch_recording`, the session log and the
  hand-off to `pull` are not, and wait for a confirmed bench device
- [SMELL] — README uses bold for emphasis, which the Epiphan style guide rules out; left as is for a developer
  README, Tim's call
- [INFO] — spec checked 2026-10-16: still 64 paths; all 8 client calls are in it and on a kb page. In the spec,
  not used: bookmarks (required `text` query parameter), storages, single touch, AFU status, presets. Unknown
  until a bench test: how a bookmark appears in the file or archive listing; whether `/schedule/events/{id}/control/extend`
  works on events that come from a CMS. No REST call returns the Date and Time protocol
- [INFO] — a separate EC20 spec exists (44 paths, camera IP base, includes `/misc/record` and PTZ presets); not
  used

Carried over from 2026-10-15, still open:
- [RISK] — `datasets` extra: only `lerobot[dataset,av-dep]==0.6.1` was verified; run `uv sync --extra datasets`
  once on the Mac
- [RISK] — `torchcodec` supports FFmpeg 4 to 8; with FFmpeg 9 LeRobot falls back to `pyav` and
  `StreamingLeRobotDataset` cannot run
- [RISK] — a non-integer file frame rate (59.94 or 29.97 Hz sources) is refused; whether Pearl writes one is open
- [SMELL] — the step table uses the shortest camera; recorded as a manifest incident when counts differ, with no
  claim about timing
- No BLOCKER. ALERTS.md stays empty.

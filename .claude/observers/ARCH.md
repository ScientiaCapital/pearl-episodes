# ARCH

Point-in-time audit, end of 2026-10-17. Format: `[LEVEL] — component — what — impact`.
Yesterday's report is in `.claude/archive/2026-10-16-OBSERVER-ARCH.md`; its open items carry over (below).

- [RISK] — Pearl REST over HTTPS — the client always uses `https://`; the kb says `http://` is the default and
  `https://` applies if HTTPS is configured on the device. A bench Pearl without HTTPS fails the first call —
  check the device's setting before `doctor` on bench day
- [DECIDED 2026-10-16] — repository hosting — the repo, the Edge Claude Kit and Fleetwatch stay in the
  ScientiaCapital GitHub org (Tim's decision); README and LICENSE keep the Epiphan Systems Inc. notice
- [RESOLVED 2026-10-17] — bench devices in Edge — an Edge sandbox team (Pearl-2, Pearl Mini, EC20) exists and the
  claude.ai connector is signed in to it; the demo fleet stays off limits for recording
- [BLOCKER for #10, owner: sandbox owner] — network path — this Mac cannot reach the sandbox devices (no answer to ping, 80,
  443), so `doctor` and `pull` cannot run; Edge start and stop still work. Needs VPN or another route
- [RISK] — two Edge teams — the same tool names act on whichever team the OAuth sign-in chose; confirm with
  `get_devices_in_my_team` before every write (now in CLAUDE.md and epiphan-safety.md)
- [SMELL] — operator session — preflight is built; start/stop through `batch_recording`, the session log and the
  hand-off to `pull` are not, and wait for a confirmed bench device
- [RESOLVED 2026-10-16] — README bold emphasis removed in #35, per the Epiphan style guide
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

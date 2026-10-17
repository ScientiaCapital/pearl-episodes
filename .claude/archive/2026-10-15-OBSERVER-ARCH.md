# ARCH

Point-in-time audit, end of 2026-10-15. Format: `[LEVEL] — component — what — impact`.

Resolved today: the LeRobot target is v3.0 (PLAN section 1 updated); `anyio` pinned; take membership is an
explicit file list; models are frozen with `extra="forbid"`, API models `extra="allow"`.

- [RISK] — `datasets` extra — only `lerobot[dataset,av-dep]==0.6.1` was installed and verified. `tensorflow`,
  `tensorflow-datasets`, `matplotlib` and `jupyterlab` are in the lock but were not installed through
  `uv sync --extra datasets` on Apple silicon — run it once on the Mac before relying on the extra
- [RISK] — video decode — `torchcodec` supports FFmpeg 4 to 8; this Mac has FFmpeg 9, so LeRobot falls back to
  `pyav` and `StreamingLeRobotDataset` (torchcodec only in 0.6.1) cannot run — notebook uses `pyav`; revisit on
  the next lerobot release
- [RISK] — export — a non-integer file frame rate (59.94 or 29.97 Hz sources) is refused; whether Pearl writes
  one is open (PLAN section 6, item 12) — bench test first
- [SMELL] — export — the step table uses the shortest camera; the format indexes cameras by frame number, which
  this project does not claim means anything about timing — recorded as a manifest incident when counts differ
- [SMELL] — session log and operator script — not built; `package` takes `--session` but nothing writes it
- No BLOCKER. ALERTS.md stays empty.

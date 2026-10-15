# ARCH

Point-in-time audit, 2026-10-15 (start of Sprint 1). Format: `[LEVEL] — component — what — impact`.

- [RISK] — export layout — `.claude/PLAN.md` §1 still shows the LeRobot v2.1 layout; the Hub copy of DROID
  (`lerobot/droid_1.0.1`) is `codebase_version v3.0` and PyPI lerobot is 0.6.1 — decided 2026-10-15: target v3.0,
  write it directly with pyarrow and verify with lerobot's loader (sprint plan, step 7)
- [RISK] — `datasets` extra — unpinned and never installed on Apple silicon; the exporter must not import it —
  core writer depends on pyarrow and numpy only; the loader test is marked and skipped without lerobot
- [SMELL] — client models — API models should be `extra="allow"` (spec may add fields), manifest models
  `extra="forbid"` and frozen; today neither is set — issue #6
- [SMELL] — take grouping — no rule in code yet for which files form a take; Sprint 1 uses an explicit
  `--files` list and never parses file names or `created` — session-log windows come post-sprint
- No BLOCKER. ALERTS.md stays empty.

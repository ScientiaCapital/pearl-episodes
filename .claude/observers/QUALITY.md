# QUALITY

Point-in-time audit, end of 2026-10-17 (`main` at a4c03a4). Format: `[LEVEL] — file:line — what — fix`.
Yesterday's report is in `.claude/archive/2026-10-16-OBSERVER-QUALITY.md`; its open items carry over (below).

2026-10-17: no code changes; docs and planning only. Secrets sweep: gitleaks scanned 35 commits, no leaks; no `.env`,
`.pem` or `.key` file in history. No CRITICAL or BLOCKER. Items below are unchanged from 2026-10-16.

2026-10-16: #29 (read-only preflight), #30 (REST re-check, kb page beside each client call), #31 (README, CLAUDE.md and
project context brought up to date). Gate green on each: ruff, 128 passed and 1 skipped, hook tests, pre-commit.
Secrets sweep: gitleaks scanned 60 commits, no leaks; no `.env`, `.pem` or `.key` file in history. No CRITICAL or
BLOCKER.

- [WARNING] — `.claude/commands/preflight.md` — a Claude session builds the scratch JSON by copying fields from
  the Edge tool results; one transcription slip gives a wrong OK or NOT READY. The live check copied by hand —
  have the command save each tool result verbatim and let the CLI read the raw responses (effort S, impact M)
- [RESOLVED 2026-10-16] — src/pearl_episodes/pearl/client.py `start_all` — without `ids` it starts every
  recorder on the device (kb: pearl-rest-api-start-and-stop-recording); `start_all` and `stop_all` now need `ids`
  or `all_recorders=True` and refuse an empty call
- [INFO] — src/pearl_episodes/operate/preflight.py — `recorder.file_format` and `recorder.size_limit` are the
  setting ids `get_channel_settings` returned on two devices; the kb pages name the rule (MP4, 500 MB) but not
  the ids. Observed, not documented — recheck after a firmware change
- [INFO] — src/pearl_episodes/operate/preflight.py — the 10 GB free-space floor is our policy, set by
  `DEFAULT_MIN_FREE_BYTES` and `--min-free-bytes`, not in `Settings`; move it when the session script needs it
- [INFO] — a variant file type such as `MP4 Fragmented` is reported `UNVERIFIED`, not failed; the kb does not say
  whether Edge accepts it — settle on the bench

Carried over from 2026-10-15, still open:
- [WARNING] — export frame sampler reads each whole file; time it on the first real 30-minute take (#10)
- [WARNING] — `package` requires `--serial`, `--model`, `--firmware`; `device_info()` could fill model and
  firmware once a device is on the bench
- [INFO] — `tests/test_lerobot_loader.py` is skipped in CI; run it in a scratch venv after any lerobot change
- [INFO] — no real Pearl file has gone through `pull`, `package` or `export`; every test uses generated clips
  and mocked transports

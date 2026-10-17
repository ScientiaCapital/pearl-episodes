# QUALITY

Point-in-time audit, end of 2026-10-15 (`main` at 29b19f5). Format: `[LEVEL] — file:line — what — fix`.

Resolved today: envelope check and `or []` fallbacks (#2), atomic downloads (#3), `doctor` exit codes (#4),
atomic manifest write (#6), the env-isolation fixture now covers every test (#13), `anyio` is a direct dependency.

- [WARNING] — src/pearl_episodes/export/lerobot_v3.py — `-count_packets` and the frame sampler read each whole
  file; fine for 500 MB segments, untested on a 30-minute 1080p file — time it on the first real take (#10)
- [WARNING] — src/pearl_episodes/episodes/manifest.py `load_manifest` — a sync file read, called through
  `to_thread` in the exporter but plain in the CLI path for `export` — wrap if it ever sits on a hot path
- [WARNING] — src/pearl_episodes/cli.py `package` — `--serial`, `--model` and `--firmware` are required flags;
  `device_info()` could fill model and firmware — add once a device is on the bench
- [INFO] — tests/test_lerobot_loader.py — skipped in CI and in the dev venv (needs the `datasets` extra); it
  passed once in a scratch venv with `lerobot[dataset,av-dep]==0.6.1` — run it after any lerobot bump
- [INFO] — no real Pearl file has ever gone through `pull`, `package` or `export`; every test uses generated
  ffmpeg test patterns and mocked transports

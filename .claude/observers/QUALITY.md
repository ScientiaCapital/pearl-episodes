# QUALITY

Point-in-time audit, 2026-10-15 (start of Sprint 1, `main` at 506874a). Format: `[LEVEL] — file:line — what — fix`.

- [CRITICAL] — src/pearl_episodes/pearl/client.py:71 — `_get_result` ignores `status` and `or []` / `or {}`
  turn a failed call into "no recordings" or empty firmware strings — issue #2, step 1 of the sprint plan
- [CRITICAL] — src/pearl_episodes/pearl/client.py:102 — `download` writes to the final path with blocking
  `open`/`write`; a dropped connection leaves a truncated file that would be hashed as good — issue #3
- [WARNING] — src/pearl_episodes/cli.py:24 — `doctor` swallows every exception and exits 0 — issue #4
- [WARNING] — src/pearl_episodes/episodes/manifest.py:39 — `manifest.write` is not atomic and blocks the loop — issue #6
- [WARNING] — tests/test_config.py:9 — the `_isolated_env` autouse fixture only covers `test_config.py`; other
  test modules can read a developer's `.env` — issue #13 (move to `tests/conftest.py`)
- [INFO] — pyproject.toml — `anyio` is used indirectly through httpx; becomes a direct dependency with #3

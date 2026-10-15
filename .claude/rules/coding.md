# Coding Rules

- Python 3.12+. `uv sync`, `uv run`. Type hints on every function. `async`/`await` for every network and disk call
  that can block. `ruff check` and `ruff format --check` clean before commit.
- `src/` layout, `pearl_episodes` package. Tests in `tests/`, pytest with `asyncio_mode = auto`.
- Settings come from `pearl_episodes.config.Settings`, never from `os.environ` directly.
- No OpenAI. No telemetry. No network calls in tests (mock `httpx` with a transport).
- Pearl REST paths are configuration until verified on a device; document the kb.epiphan.com page beside each
  endpoint. Never invent fields.
- Dependencies: pin what we verify; leave the `datasets` extra unpinned until the first successful install.

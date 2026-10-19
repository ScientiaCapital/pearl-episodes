# Contributing

pearl-episodes is a small, private Epiphan project. Contributions that keep it honest (documented facts only),
safe (every device change approved) and small are the most welcome.

## What helps most, in order

1. The client hardening and `pull` work at the top of `.claude/BACKLOG.md`.
2. Bench results from a real Pearl: actual REST responses, error cases, the codec test in `docs/HARDWARE.md`.
   Redact them first (rule 4 below).
3. The LeRobot export and the notebook that opens a Pearl episode beside a DROID episode.
4. Anything else: open an issue first for anything large.

## Set up

```bash
uv sync --group dev
uv run pytest -q
bash tests/hook-test.sh
uvx pre-commit install      # runs gitleaks, ruff, shellcheck, actionlint and zizmor on every commit
```

Most of the code can be worked on without a device: the tests mock `httpx` and make no network calls. For bench
work, copy `.env.example` to `.env` and point it at your own Pearl, not a shared one.

## Rules

1. **Documented facts only.** Pearl and Edge behaviour comes from Epiphan's OpenAPI spec and kb.epiphan.com, cited
   beside the code. If the docs don't cover it, it's a bench test or an open question, not a fact.
2. **No timing or alignment claims** between cameras or devices, anywhere. Record `clock_source`; nothing more.
3. **Device changes need a person.** Don't weaken the Edge write guard, the redaction hook or the permissions in
   `.claude/settings.json`. They come from the Epiphan Edge Claude Kit; change them there first.
4. **No real data.** No recordings, frames, serials, IPs, device or room names, people, internal messages,
   customer data or CRM figures in code, fixtures, issues or PRs. Use placeholders.
5. **Secrets in `.env` only**, read through `Settings`. gitleaks runs in pre-commit and CI.
6. **Code style.** Python 3.12+, async for all I/O, type hints on every function, `ruff` clean, no OpenAI.

## Commits and pull requests

- [Conventional Commits](https://www.conventionalcommits.org/) with a scope: `fix(client): ...`,
  `feat(packager): ...`, `docs(readme): ...`, `ci: ...`, `test(hooks): ...`.
- One concern per PR, from a branch. Fill in the PR template's Evidence section with commands you ran and what
  they printed. CI must be green: lint, tests on Linux and macOS, the hook tests and the secrets scan.

## Using an AI assistant

Fine and welcome. Point it at [AGENTS.md](AGENTS.md). You are responsible for every line you submit.

## Security issues

See [SECURITY.md](SECURITY.md). Contributions are made as Epiphan work, belong to Epiphan Systems Inc. and are licensed under the Apache
License 2.0 (see [LICENSE](LICENSE)).

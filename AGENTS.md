# AGENTS.md

Instructions for AI coding assistants (Claude Code, Codex, Cursor and others) working in this repo. Humans:
[CONTRIBUTING.md](CONTRIBUTING.md) has the same rules in longer form.

## What this is

pearl-episodes records robot-learning demonstrations on Epiphan Pearl, runs the capture stations through
Epiphan Edge, and packages each take as an episode (LeRobot, RLDS). Python 3.12, uv, ruff, pytest with
`asyncio_mode = auto`. Package in `src/pearl_episodes/`. CLI: `pearl-episodes doctor | recorders | list | pull | package | export | preflight`
(RLDS export is not built yet). Private, Epiphan-owned.

## Commands

```bash
uv sync --group dev
uv run pytest -q                       # unit tests, no network; ffmpeg and ffprobe must be installed
bash tests/hook-test.sh                # Edge write guard, redaction, secrets hook, permission rules
uv run ruff check . && uv run ruff format --check .
uvx pre-commit run --all-files         # plus gitleaks, shellcheck, actionlint, zizmor
```

## Hard rules

1. **No claim about timing, sync or alignment** between cameras or devices, in code, comments, docs, commit
   messages or output. Record `clock_source` and leave it there.
2. **Pearl REST: only documented calls and fields.** Use what Epiphan's OpenAPI spec and the kb.epiphan.com pages
   say (`docs/ARCHITECTURE.md` lists the verified surface). Never invent endpoints, fields, ports or firmware
   behaviour; cite the kb page beside a new call. Product facts come from the kb, never from memory.
3. **Epiphan Edge writes need a person.** Never call a write tool without the maintainer's approval in that
   session, naming device, channel and effect. Never weaken `.claude/hooks/epiphan-write-guard.sh`,
   `.claude/hooks/epiphan-redact.sh` or the `permissions` in `.claude/settings.json`; those hooks are copied from
   the Edge Claude Kit and are fixed there first. The visible Edge team may be Epiphan's shared demo fleet.
4. **Secrets stay in `.env`**, read through `pearl_episodes.config.Settings`, never `os.environ`. Passwords are
   `SecretStr`. No secret, stream key or credentialed URL in code, fixtures, logs or output.
5. **No real data in the repo.** No recordings, frames, device serials, IPs, device or room names, people, internal
   messages, customer data, CRM figures or Drive document contents in code, fixtures, docs, issues, PRs or commit
   messages. Use placeholders like `TEST-SERIAL-0001` and "Room 204 Pearl Mini". Recordings and episodes are
   gitignored and stay on the machine they were pulled to.
6. **Async for every network and blocking disk call; type hints on every function.** No network in tests: mock
   `httpx` with a transport.
7. **No OpenAI.** If a model is ever needed: Anthropic direct, or DeepSeek, Qwen or Groq via OpenRouter.
8. **Unannounced hardware is not a spec.** The next Pearl is the intended production station; nothing in code or
   docs depends on, or states, its specs until Product publishes them. Camera and channel counts are data.

## Style

- Conventional Commits with scopes (`fix(client):`, `feat(packager):`, `docs(readme):`). One concern per PR.
- Work on a branch and open a PR; CI must be green. The PR template's Evidence section must show commands you
  actually ran and their output.
- Plain words in docs. Say what is documented, what is a bench test and what is unknown.

## Map

| Path | What it does |
|---|---|
| `src/pearl_episodes/pearl/client.py` | Async Pearl REST client (verified paths only) |
| `src/pearl_episodes/episodes/manifest.py` | Episode manifest model, SHA-256 hashing |
| `src/pearl_episodes/episodes/pull.py` | `pull`: idempotent on file id, atomic |
| `src/pearl_episodes/episodes/packager.py` | Packages a take by remux; writes `manifest.json` and `hashes.txt` |
| `src/pearl_episodes/media/ffmpeg.py` | ffprobe and lossless concat wrappers |
| `src/pearl_episodes/operate/preflight.py` | Read-only preflight over Edge tool output (`/preflight`) |
| `src/pearl_episodes/export/lerobot_v3.py` | LeRobot v3.0 export |
| `src/pearl_episodes/config.py` | `Settings` from `.env` (`PEARL_*`) |
| `src/pearl_episodes/cli.py` | The CLI |
| `.claude/hooks/` | Edge write guard and redaction (from the Edge Claude Kit), secrets hook |
| `tests/hook-test.sh`, `tests/redaction-cases.json` | Hook and permission tests; redaction cases shared with Fleetwatch |
| `docs/ARCHITECTURE.md` | Verified REST surface, manifest, rules, open product questions |
| `docs/HARDWARE.md` | Bench and PoC station, with kb sources |
| `.claude/PLAN.md` | Design and build order |

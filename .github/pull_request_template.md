## What and why

<!-- One concern per PR. Link the issue if there is one. -->

## Evidence

<!-- The commands you ran and what they printed. Required. -->

```
uv run python -m pytest -q
bash tests/hook-test.sh
```

## Checklist

- [ ] PR title follows Conventional Commits (`fix(scope): ...`); it becomes the squash commit
- [ ] No real device names, IDs, IPs, serials, stream keys, people or recordings in code, fixtures or this PR
- [ ] No internal messages, customer data, CRM figures or Drive file contents in code, docs or commits
- [ ] No claim about timing or alignment across cameras or devices (record `clock_source`, nothing more)
- [ ] Edge write guard and redaction unchanged, or changed in the Edge Claude Kit first
- [ ] Every Pearl REST call is on the verified list in `docs/ARCHITECTURE.md`, with its kb page
- [ ] Docs updated if behaviour or setup changed

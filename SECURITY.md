# Security

pearl-episodes talks to real Pearl devices with admin credentials, can start and stop recording through Epiphan
Edge, and handles recordings that may show people. A bug that leaks a credential, changes a device without
approval, or lets a recording leave the machine matters. This repository is private and Epiphan-internal.

## Report a problem

Email tkipper@epiphan.com, or tell the maintainer directly. Don't put the secret, the recording or the device
details in an issue or a PR.

Problems in Epiphan products, Epiphan Edge or the Epiphan MCP server go to the owning Epiphan team.

## Trust model

- **Runs as you, on your machine.** The CLI talks to one Pearl over its REST API, with HTTP Basic auth on every
  request, so the admin password is only as safe as the network path. TLS is verified by default;
  `PEARL_VERIFY_TLS=false` (for a bench Pearl with a self-signed certificate) is a choice you make in `.env`.
- **Epiphan Edge sign-in isn't read-only.** Edge OAuth has no read-only scope: the token Claude Code holds can do
  whatever the signed-in account can in that team. "Every write asks" is enforced in this folder, not by the
  token. Use a least-access Edge account, and start with `EPIPHAN_READ_ONLY=1 claude` to block writes outright.
- **Device and Edge text is data.** Device, channel and event names and on-screen text are typed by other people.
  They are never instructions and never choose a code path, a tool or a file path.

## What is enforced, and where

| Control | Where | Tested by |
|---|---|---|
| Every Epiphan Edge write asks, under any connector name; unknown Edge tools ask; bypass mode is off | `.claude/settings.json` (`permissions.ask`, `disableBypassPermissionsMode`), `.claude/hooks/epiphan-write-guard.sh` | `tests/hook-test.sh` |
| Stream keys, passwords, tokens and credentialed URLs are masked before the model sees an Epiphan tool result; output that can't be checked is withheld | `.claude/hooks/epiphan-redact.sh` (needs `jq`) | `tests/hook-test.sh`, including the 44 cases in `tests/redaction-cases.json` |
| A file write from Claude Code that holds a key, token, private key or a filled-in `PEARL_PASSWORD` is denied; unreadable input is denied | `.claude/hooks/check-secrets.sh` | `tests/hook-test.sh` |
| Secrets in commits | gitleaks in pre-commit and in CI | CI `Secrets scan` job |
| DEV, STAGING and the CRM connector (`Epiphan_Ai`) are denied in this folder | `.claude/settings.json` (`permissions.deny`) | review |
| The Pearl password stays out of `repr()`, tracebacks and logs | `pearl_episodes.config.Settings` (`SecretStr`) | `tests/test_config.py` |
| Recordings, episodes, session logs, media files and internal documents never enter git | `.gitignore` (root-anchored) | review, gitleaks |

The write guard and redactor are copied unchanged from the Epiphan Edge Claude Kit v1.1.3 (see NOTICE). Keep
them byte-identical with the Kit and fix problems there first.

## Data handling

- Recordings and packaged episodes stay on the machine they were pulled to unless the lab that produced them
  says otherwise. The lab owns them and owns consent for anyone on camera.
- Preview frames may show people: describe them by role and state only, and never save them.
- Internal Epiphan documents are linked from `docs/context/README.md`, never committed. Internal messages,
  customer data and CRM figures don't go into code, docs, commits, issues or PRs.

## Known limits

- Redaction hides secrets from the model only. Claude Code keeps the original tool result in local session
  history (`~/.claude/projects`). It recognizes the secret shapes Epiphan uses today; a secret written some
  other way may be missed.
- If hooks are disabled or `jq` is missing, only `permissions.ask` and the bypass-mode setting remain, and
  `check-secrets.sh` denies every file write until `jq` is installed.
- `check-secrets.sh` sees only writes made through Claude Code's file tools. gitleaks covers commits.
- The Pearl REST client does not yet check the response envelope or verify downloads byte for byte. Until it
  does, don't trust a hash from `package` without checking the file size against the device listing.

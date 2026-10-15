# Security

This project talks to real Epiphan devices and an Epiphan Edge team.

- Never commit `.env`, device passwords, stream keys or credentialed RTMP/SRT URLs. The pre-commit hook and `.claude/hooks/check-secrets.sh` look for them, and `.claude/hooks/epiphan-redact.py` masks keys in MCP results.
- Recordings and packaged episodes are gitignored. They may contain people. The lab that produced them owns them.
- Report a problem to tkipper@epiphan.com.

"""Append-only operator session log: one JSON line per action in `sessions/<session_id>.jsonl`.

The shape (`.claude/PLAN.md` section 5) is `machine_ts`, `tool`, `args`, `result_summary`, `warnings`, plus
an optional take `verdict` (`keep` or `discard`) and a note. `machine_ts` is this computer's clock and says
nothing about any device's clock, or about timing between cameras or devices.

The log names devices and operators, so `sessions/` is gitignored. Entries are summaries, never raw tool
output: one that holds a credentialed URL is refused.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from anyio import to_thread
from pydantic import BaseModel, ConfigDict, Field, model_validator

from pearl_episodes.operate.preflight import PreflightReport

Verdict = Literal["keep", "discard"]

SESSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
# `scheme://user:password@host`: a credentialed URL, which never belongs in a log (hard rule 4).
CREDENTIALED_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^/\s:@]*:[^/\s@]*@")


class LogEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    machine_ts: str = Field(description="This computer's clock, UTC, written when the entry was made")
    tool: str
    args: dict[str, str] = Field(default_factory=dict)
    result_summary: str
    warnings: list[str] = Field(default_factory=list, description="Verbatim from the tool that reported them")
    verdict: Verdict | None = None
    note: str = ""

    @classmethod
    def now(cls, tool: str, result_summary: str, **fields: Any) -> LogEntry:
        return cls(
            machine_ts=datetime.now(UTC).isoformat(timespec="seconds"),
            tool=tool,
            result_summary=result_summary,
            **fields,
        )

    @model_validator(mode="after")
    def _no_credentialed_urls(self) -> LogEntry:
        texts = [self.tool, self.result_summary, self.note, *self.args.values(), *self.warnings]
        if any(CREDENTIALED_URL.search(t) for t in texts):
            raise ValueError("log entries must not contain a credentialed URL; summarize instead")
        return self


class SessionLog:
    """The log file for one session. `append` adds one line and never rewrites an earlier one."""

    def __init__(self, directory: Path, session_id: str) -> None:
        if not SESSION_ID.match(session_id):
            raise ValueError(f"not a valid session id: {session_id!r}")
        self.path = directory / f"{session_id}.jsonl"

    async def append(self, entry: LogEntry) -> None:
        await to_thread.run_sync(self._append_line, entry.model_dump_json() + "\n")

    async def read(self) -> list[LogEntry]:
        text = await to_thread.run_sync(self.path.read_text)
        return [LogEntry.model_validate_json(line) for line in text.splitlines() if line]

    def _append_line(self, line: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())


def preflight_entry(report: PreflightReport, channels: Sequence[str]) -> LogEntry:
    """One log line for a preflight run: ready or not, which checks failed, and the verbatim warnings."""
    failed = sorted({c.name for ch in report.channels for c in ch.checks if c.status == "fail"})
    blocked = sum(not ch.ok for ch in report.channels)
    summary = (
        "ready"
        if report.ok
        else f"not ready: {blocked} of {len(report.channels)} channels ({', '.join(failed)})"
    )
    warnings = list(dict.fromkeys(w for ch in report.channels for w in ch.warnings))
    return LogEntry.now("preflight", summary, args={"channels": ",".join(channels)}, warnings=warnings)

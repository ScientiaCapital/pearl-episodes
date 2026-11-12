"""`pull`: download new archive files for one recorder, idempotent on file id.

Files land in `<folder>/<file_id>.<extension>`. `<folder>/index.jsonl` gets one JSON line per pulled file,
written only after the file is complete and hashed, so an interrupted run never indexes a missing or partial
file. A crash in the middle of an append can leave the last line cut short: `load_index` ignores that line and
the next append replaces it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from anyio import to_thread

from pearl_episodes.episodes.manifest import sha256_of_async
from pearl_episodes.pearl.client import SAFE_ID, PearlClient, RecordingFile, UnsafeIdError

INDEX_NAME = "index.jsonl"


@dataclass
class PullReport:
    downloaded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    still_recording: list[str] = field(default_factory=list)


def _file_name(file: RecordingFile) -> str:
    """`<id>.<extension>`. Both come from the device and become a path part, so they must be plain names."""
    for part in (file.id, file.extension):
        if part is not None and not SAFE_ID.fullmatch(part):
            raise UnsafeIdError(f"unsafe file id or extension from device: {part!r}")
    return file.id if file.extension is None else f"{file.id}.{file.extension}"


def _torn_tail(text: str) -> str:
    """The unfinished last line of `text`: no newline and not valid JSON. Empty if there is none."""
    tail = text[text.rfind("\n") + 1 :]
    if not tail.strip():
        return ""
    try:
        json.loads(tail)
    except ValueError:
        return tail
    return ""


def load_index(folder: Path) -> list[dict[str, Any]]:
    """The pulled-file index for `folder`; empty when nothing has been pulled yet. A torn last line is
    ignored; a broken line anywhere else raises `ValueError`."""
    path = folder / INDEX_NAME
    if not path.exists():
        return []
    text = path.read_text()
    text = text[: len(text) - len(_torn_tail(text))]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _append_index(folder: Path, entry: dict[str, Any]) -> None:
    """Append one line. A torn last line is cut off first, and a complete one missing its newline gets one."""
    path = folder / INDEX_NAME
    with path.open("a+") as fh:
        fh.seek(0)
        text = fh.read()
        torn = _torn_tail(text)
        if torn:
            fh.truncate(len(text.encode()) - len(torn.encode()))
        elif text and not text.endswith("\n"):
            fh.write("\n")
        fh.write(json.dumps(entry) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


async def pull(client: PearlClient, recorder_id: str, folder: Path) -> PullReport:
    """Download every archive file of `recorder_id` not already in the index. A file still `recording` or
    `uploading` is reported and left for a later run."""
    known = {e["id"] for e in await to_thread.run_sync(load_index, folder)}
    report = PullReport()
    for file in await client.list_recordings(recorder_id):
        if file.id in known:
            report.skipped.append(file.id)
        elif file.recording or file.uploading:
            report.still_recording.append(file.id)
        else:
            name = _file_name(file)
            dest = await client.download(recorder_id, file, folder / name)
            entry = {
                **file.model_dump(include={"id", "name", "extension", "created", "duration", "size"}),
                "recorder": file.recorder,
                "event_id": file.event_id,
                "sha256": await sha256_of_async(dest),
                "path": name,
            }
            await to_thread.run_sync(_append_index, folder, entry)
            report.downloaded.append(file.id)
    return report

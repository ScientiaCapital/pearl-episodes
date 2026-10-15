"""`pull`: download new archive files for one recorder, idempotent on file id.

Files land in `<folder>/<file_id>.<extension>`. `<folder>/index.jsonl` gets one JSON line per pulled file,
written only after the file is complete and hashed, so an interrupted run never indexes a missing or partial
file.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from anyio import to_thread

from pearl_episodes.episodes.manifest import sha256_of_async
from pearl_episodes.pearl.client import PearlClient, RecordingFile

INDEX_NAME = "index.jsonl"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass
class PullReport:
    downloaded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    still_recording: list[str] = field(default_factory=list)


def _file_name(file: RecordingFile) -> str:
    """`<id>.<extension>`. Both come from the device and become a path part, so they must be plain names."""
    for part in (file.id, file.extension):
        if part is not None and not _SAFE_NAME.fullmatch(part):
            raise ValueError(f"unsafe file id or extension from device: {part!r}")
    return file.id if file.extension is None else f"{file.id}.{file.extension}"


def load_index(folder: Path) -> list[dict[str, Any]]:
    """The pulled-file index for `folder`; empty when nothing has been pulled yet."""
    path = folder / INDEX_NAME
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _append_index(folder: Path, entry: dict[str, Any]) -> None:
    with (folder / INDEX_NAME).open("a") as fh:
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

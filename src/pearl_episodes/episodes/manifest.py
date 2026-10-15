"""Per-take episode manifest: file hashes plus context the product does not record (task, operator, scene,
clock source)."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Literal

from anyio import to_thread
from pydantic import BaseModel, Field

ClockSource = Literal["ntp", "ptp", "unknown"]


class CameraFile(BaseModel):
    channel_id: str
    channel_name: str
    file_name: str
    file_size: int
    sha256: str
    duration_s: float | None = None


class EpisodeManifest(BaseModel):
    episode_id: str
    device_serial: str
    device_model: str
    firmware: str
    start_time: datetime = Field(description="Device clock, as the archive listing reports it")
    cameras: list[CameraFile]
    task_label: str = ""
    operator: str = ""
    scene: str = ""
    clock_source: ClockSource = "unknown"
    notes: str = ""
    schema_version: int = 1

    async def write(self, directory: Path) -> Path:
        """Write `manifest.json` atomically (temp file, then rename) in a worker thread."""
        return await to_thread.run_sync(
            write_text_atomic, directory / "manifest.json", self.model_dump_json(indent=2)
        )


def write_text_atomic(path: Path, text: str) -> Path:
    """Write `text` to `<path>.tmp` and rename it over `path`, so a reader never sees a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)
    return path


def sha256_of(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def sha256_of_async(path: Path) -> str:
    """`sha256_of` off the event loop; a 500 MB segment takes a while to read."""
    return await to_thread.run_sync(sha256_of, path)

"""Per-take episode manifest: file hashes plus context the product does not record (task, operator, scene,
clock source)."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Literal

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

    def write(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "manifest.json"
        path.write_text(self.model_dump_json(indent=2))
        return path


def sha256_of(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()

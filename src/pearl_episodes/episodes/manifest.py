"""Per-take episode manifest, schema version 2: ordered segments per camera, derived files, incidents, and the
context the product does not record (task, operator, scene, clock source).

Times are raw device text. Nothing here parses `created` into a guessed timezone or says anything about timing
between cameras or devices; `clock_source` is recorded as read and never interpreted.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Annotated, Literal

from anyio import to_thread
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator

ClockSource = Literal["ntp", "ptp", "manual", "unknown"]

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


def _check_safe_relative_path(value: str) -> str:
    parts = value.split("/")
    if not value or value.startswith("/") or "\\" in value or any(p in ("", ".", "..") for p in parts):
        raise ValueError(f"not a safe relative path: {value!r}")
    return value


SafeRelPath = Annotated[str, AfterValidator(_check_safe_relative_path)]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Segment(_Frozen):
    """One Pearl file of a take. A take that rolled over at 30 minutes or 500 MB has several."""

    seq: int = Field(ge=0)
    file_id: str
    path: SafeRelPath = Field(description="Original file, relative to the episode directory")
    created: str = Field(description="Raw device text from the archive listing")
    duration: int | None = None
    size: int = Field(ge=0)
    sha256: Sha256
    recorder_id: str
    event_id: str | None = None


class Camera(_Frozen):
    channel_id: str
    channel_name: str
    segments: list[Segment] = Field(min_length=1)

    @model_validator(mode="after")
    def _segments_are_numbered_in_order(self) -> Camera:
        if [s.seq for s in self.segments] != list(range(len(self.segments))):
            raise ValueError("segment seq values must be exactly 0..n-1 in order")
        return self


class Derived(_Frozen):
    """A file made from the originals (joined video, export copy), with the tool that made it."""

    path: SafeRelPath
    sha256: Sha256
    tool: str
    version: str


class Incident(_Frozen):
    """Something a tool reported during the take, copied verbatim."""

    ts: str
    source: str
    text: str


class EpisodeManifest(_Frozen):
    schema_version: Literal[2] = 2
    episode_id: str
    device_serial: str
    device_model: str
    firmware: str
    start_time: str = Field(description="Raw `created` of the first segment, device clock, never parsed")
    cameras: list[Camera]
    derived: list[Derived] = []
    session_id: str | None = None
    incidents: list[Incident] = []
    task_label: str = ""
    operator: str = ""
    scene: str = ""
    clock_source: ClockSource = "unknown"
    notes: str = ""

    async def write(self, directory: Path) -> Path:
        """Write `manifest.json` atomically (temp file, then rename) in a worker thread."""
        return await to_thread.run_sync(
            write_text_atomic, directory / "manifest.json", self.model_dump_json(indent=2)
        )


def load_manifest(path: Path) -> EpisodeManifest:
    """Read a v2 manifest, or upgrade a v1 one (one file per camera) to one segment per camera."""
    data = json.loads(path.read_text())
    if data.get("schema_version") == 1:
        data = _upgrade_v1(data)
    return EpisodeManifest.model_validate(data)


def _upgrade_v1(v1: dict) -> dict:
    start_time = str(v1["start_time"])
    cameras = [
        {
            "channel_id": c["channel_id"],
            "channel_name": c["channel_name"],
            "segments": [
                {
                    "seq": 0,
                    "file_id": c["file_name"],
                    "path": c["file_name"],
                    "created": start_time,
                    "duration": None if c.get("duration_s") is None else int(c["duration_s"]),
                    "size": c["file_size"],
                    "sha256": c["sha256"],
                    "recorder_id": "",
                    "event_id": None,
                }
            ],
        }
        for c in v1["cameras"]
    ]
    kept = {
        k: v1[k]
        for k in (
            "episode_id",
            "device_serial",
            "device_model",
            "firmware",
            "task_label",
            "operator",
            "scene",
            "clock_source",
            "notes",
        )
        if k in v1
    }
    return {**kept, "schema_version": 2, "start_time": start_time, "cameras": cameras}


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

"""Package a take as an episode directory: originals kept untouched, one joined video per camera made by
lossless remux, `manifest.json` and `hashes.txt`.

A take that Pearl rolled over at 30 minutes or 500 MB is several files. Segments are ordered by the device's
raw `created` text, then by file id; file names are never parsed. If the segments of a camera cannot be joined
without re-encoding, the take is exported as one sub-episode per segment and the manifest says why.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from anyio import to_thread

from pearl_episodes.episodes.manifest import (
    Camera,
    ClockSource,
    Derived,
    EpisodeManifest,
    Incident,
    Segment,
    sha256_of_async,
    write_text_atomic,
)
from pearl_episodes.episodes.pull import load_index
from pearl_episodes.media.ffmpeg import RemuxError, concat_copy, ffmpeg_version, probe

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

# kb pearl-family/about-recording, quoted exactly; the manifest says nothing more about continuity.
ROLLOVER_NOTE = (
    'Pearl rolled this recording into several files. kb pearl-family/about-recording: "When the time or file '
    "size limit is reached, the current recording is saved and a new recording file starts automatically "
    'without losing any content."'
)


@dataclass(frozen=True)
class CameraInput:
    """One camera of a take: where `pull` put its files and which of them belong to the take."""

    channel_id: str
    channel_name: str
    recorder_id: str
    folder: Path
    file_ids: list[str]


@dataclass(frozen=True)
class TakeLabels:
    """What the product does not record, supplied by the operator and by Edge."""

    device_serial: str
    device_model: str
    firmware: str
    task_label: str = ""
    operator: str = ""
    scene: str = ""
    clock_source: ClockSource = "unknown"
    notes: str = ""
    session_id: str | None = None


def hashes_text(manifest: EpisodeManifest) -> str:
    """`<sha256>  <path>` for every original segment, then every derived file.

    `shasum -a 256 -c hashes.txt` passes from the episode directory."""
    lines = [f"{s.sha256}  {s.path}\n" for c in manifest.cameras for s in c.segments]
    lines += [f"{d.sha256}  {d.path}\n" for d in manifest.derived]
    return "".join(lines)


async def write_hashes(manifest: EpisodeManifest, directory: Path) -> Path:
    return await to_thread.run_sync(write_text_atomic, directory / "hashes.txt", hashes_text(manifest))


async def package(manifest: EpisodeManifest, directory: Path) -> Path:
    """Write manifest and hashes into `directory`."""
    await manifest.write(directory)
    await write_hashes(manifest, directory)
    return directory


def _safe(name: str, what: str) -> str:
    if not _SAFE_NAME.fullmatch(name):
        raise ValueError(f"unsafe {what}: {name!r}")
    return name


def _sort_key(entry: dict[str, Any]) -> tuple[str, str]:
    return (entry.get("created") or "", entry["id"])


async def _select(camera: CameraInput) -> list[dict[str, Any]]:
    index = {e["id"]: e for e in await to_thread.run_sync(load_index, camera.folder)}
    missing = [fid for fid in camera.file_ids if fid not in index]
    if missing:
        raise ValueError(f"not pulled: {', '.join(missing)} (recorder {camera.recorder_id})")
    return sorted((index[fid] for fid in camera.file_ids), key=_sort_key)


async def _build(
    staging: Path,
    episode_id: str,
    selection: list[tuple[CameraInput, list[dict[str, Any]]]],
    labels: TakeLabels,
    *,
    notes: str,
    incidents: list[Incident],
) -> None:
    """Fill `staging` with originals, joined videos, manifest and hashes. Raises `RemuxError` if a camera's
    segments cannot be joined."""
    version = await ffmpeg_version()
    cameras: list[Camera] = []
    derived: list[Derived] = []
    for camera, entries in selection:
        channel = _safe(camera.channel_id, "channel id")
        segments: list[Segment] = []
        for seq, entry in enumerate(entries):
            name = entry["path"]
            if "/" in name:
                raise ValueError(f"unsafe index path: {name!r}")
            dest = staging / "source" / channel / name
            await to_thread.run_sync(dest.parent.mkdir, 0o755, True, True)
            await to_thread.run_sync(shutil.copy2, camera.folder / name, dest)
            if await sha256_of_async(dest) != entry["sha256"]:
                raise ValueError(
                    f"hash of {name} differs from the pull index; was the file changed after the pull?"
                )
            segments.append(
                Segment(
                    seq=seq,
                    file_id=entry["id"],
                    path=f"source/{channel}/{name}",
                    created=entry.get("created") or "",
                    duration=entry.get("duration"),
                    size=entry["size"],
                    sha256=entry["sha256"],
                    recorder_id=camera.recorder_id,
                    event_id=entry.get("event_id"),
                )
            )
        joined = staging / "joined" / f"{channel}.mp4"
        await concat_copy([staging / s.path for s in segments], joined)
        await probe(joined)
        derived.append(
            Derived(
                path=f"joined/{channel}.mp4",
                sha256=await sha256_of_async(joined),
                tool="ffmpeg",
                version=version,
            )
        )
        cameras.append(
            Camera(channel_id=camera.channel_id, channel_name=camera.channel_name, segments=segments)
        )
    manifest = EpisodeManifest(
        episode_id=episode_id,
        device_serial=labels.device_serial,
        device_model=labels.device_model,
        firmware=labels.firmware,
        start_time=min(c.segments[0].created for c in cameras),
        cameras=cameras,
        derived=derived,
        session_id=labels.session_id,
        incidents=incidents,
        task_label=labels.task_label,
        operator=labels.operator,
        scene=labels.scene,
        clock_source=labels.clock_source,
        notes=notes,
    )
    await package(manifest, staging)


async def _finish(out_root: Path, episode_id: str, build: Callable[[Path], Awaitable[None]]) -> Path:
    """Build into a staging directory and rename it into place, so a failure leaves nothing half-made."""
    final = out_root / _safe(episode_id, "episode id")
    if final.exists():
        raise FileExistsError(f"{final} already exists; episodes are never overwritten")
    staging = out_root / f".{episode_id}.building"
    await to_thread.run_sync(shutil.rmtree, staging, True)
    try:
        await to_thread.run_sync(staging.mkdir, 0o755, True, True)
        await build(staging)
        await to_thread.run_sync(staging.rename, final)
    except BaseException:
        await to_thread.run_sync(shutil.rmtree, staging, True)
        raise
    return final


def _builder(
    episode_id: str,
    selection: list[tuple[CameraInput, list[dict[str, Any]]]],
    labels: TakeLabels,
    notes: str,
    incidents: list[Incident],
) -> Callable[[Path], Awaitable[None]]:
    async def build(staging: Path) -> None:
        await _build(staging, episode_id, selection, labels, notes=notes, incidents=incidents)

    return build


async def package_take(
    cameras: list[CameraInput], labels: TakeLabels, out_root: Path, episode_id: str | None = None
) -> list[Path]:
    """Package one take. Returns one episode directory, or one per segment when a camera's segments cannot be
    joined by remux."""
    selection = [(camera, await _select(camera)) for camera in cameras]
    first = min((entries[0] for _, entries in selection), key=_sort_key)
    stamp = re.sub(r"[^A-Za-z0-9]+", "-", first.get("created") or first["id"]).strip("-")
    episode_id = episode_id or f"{labels.device_serial}-{stamp}"
    notes = labels.notes
    if any(len(entries) > 1 for _, entries in selection):
        notes = f"{notes}\n{ROLLOVER_NOTE}".strip()
    try:
        return [await _finish(out_root, episode_id, _builder(episode_id, selection, labels, notes, []))]
    except RemuxError as error:
        reason = str(error)

    count = max(len(entries) for _, entries in selection)
    note = f"{labels.notes}\nThe segments could not be joined by remux; exported as {count} sub-episodes."
    incident = Incident(
        ts=datetime.now(UTC).isoformat(timespec="seconds"), source="pearl-episodes", text=reason
    )
    episodes: list[Path] = []
    for k in range(count):
        part = [(camera, [entries[k]]) for camera, entries in selection if len(entries) > k]
        part_id = f"{episode_id}-part{k:02d}"
        build = _builder(part_id, part, labels, note.strip(), [incident])
        episodes.append(await _finish(out_root, part_id, build))
    return episodes

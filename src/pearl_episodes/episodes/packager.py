"""Write one episode directory from a prepared manifest: `manifest.json` and `hashes.txt`.

Grouping files into takes, copying video and the LeRobot/RLDS layouts are not built yet (`.claude/PLAN.md`).
"""

from __future__ import annotations

from pathlib import Path

from anyio import to_thread

from pearl_episodes.episodes.manifest import CameraFile, EpisodeManifest, sha256_of, write_text_atomic


def camera_file_from(path: Path, channel_id: str, channel_name: str, duration_s: float | None) -> CameraFile:
    return CameraFile(
        channel_id=channel_id,
        channel_name=channel_name,
        file_name=path.name,
        file_size=path.stat().st_size,
        sha256=sha256_of(path),
        duration_s=duration_s,
    )


async def write_hashes(manifest: EpisodeManifest, directory: Path) -> Path:
    text = "".join(f"{c.sha256}  {c.file_name}\n" for c in manifest.cameras)
    return await to_thread.run_sync(write_text_atomic, directory / "hashes.txt", text)


async def package(manifest: EpisodeManifest, directory: Path) -> Path:
    """Write manifest and hashes into `directory`."""
    await manifest.write(directory)
    await write_hashes(manifest, directory)
    return directory

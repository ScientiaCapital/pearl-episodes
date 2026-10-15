"""Write one episode directory from a prepared manifest: `manifest.json` and `hashes.txt`.

Grouping files into takes, remuxing video and the LeRobot/RLDS layouts are built in later steps
(`.claude/PLAN.md`).
"""

from __future__ import annotations

from pathlib import Path

from anyio import to_thread

from pearl_episodes.episodes.manifest import EpisodeManifest, write_text_atomic


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

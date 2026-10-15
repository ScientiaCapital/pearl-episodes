"""Make a synthetic two-camera take, package it and export it, so the notebook runs before a real Pearl take
exists. The clips are ffmpeg test patterns, not Pearl footage, and the manifest says so.

    uv run python scripts/make_synthetic_take.py /tmp/pe-demo

Prints the LeRobot directory, `<out_dir>/episodes/synthetic-0001/lerobot`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from pearl_episodes.episodes.manifest import sha256_of
from pearl_episodes.episodes.packager import CameraInput, TakeLabels, package_take
from pearl_episodes.export.lerobot_v3 import export_lerobot_v3

CAMERAS = (("1", "Wide Cam", "testsrc"), ("2", "Side Cam", "smptebars"))


async def _make_clip(path: Path, source: str, *, seconds: int, size: str, fps: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"{source}=size={size}:rate={fps}",
        "-frames:v", str(seconds * fps), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
        stdin=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )  # fmt: skip
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {err.decode(errors='replace')[-300:]}")


def _pulled_folder(folder: Path, clip: Path, created: str) -> Path:
    """The folder `pull` would leave: `1.mp4` and an `index.jsonl` line for it."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "1.mp4").write_bytes(clip.read_bytes())
    entry = {
        "id": "1", "name": clip.stem, "extension": "mp4", "created": created, "duration": None,
        "size": clip.stat().st_size, "recorder": folder.name, "event_id": None,
        "sha256": sha256_of(clip), "path": "1.mp4",
    }  # fmt: skip
    (folder / "index.jsonl").write_text(json.dumps(entry) + "\n")
    return folder


async def build(out_dir: Path, *, seconds: int = 10, size: str = "1280x720", fps: int = 30) -> Path:
    """Generate, package and export the take under `out_dir`; return the LeRobot directory."""
    cameras = []
    for channel_id, name, source in CAMERAS:
        clip = out_dir / "generated" / f"{channel_id}.mp4"
        await _make_clip(clip, source, seconds=seconds, size=size, fps=fps)
        folder = _pulled_folder(out_dir / "recordings" / channel_id, clip, f"synthetic-{channel_id}")
        cameras.append(CameraInput(channel_id, name, channel_id, folder, ["1"]))
    labels = TakeLabels(
        device_serial="TEST-SERIAL-0001",
        device_model="synthetic",
        firmware="none",
        task_label="synthetic test pattern",
        notes="Synthetic take: ffmpeg test patterns, not Pearl footage.",
    )
    [episode] = await package_take(cameras, labels, out_dir / "episodes", episode_id="synthetic-0001")
    return await export_lerobot_v3(episode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Make a synthetic two-camera take and export it for LeRobot."
    )
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--seconds", type=int, default=10)
    parser.add_argument("--size", default="1280x720")
    parser.add_argument("--fps", type=int, default=30)
    args = parser.parse_args(argv)
    print(asyncio.run(build(args.out_dir, seconds=args.seconds, size=args.size, fps=args.fps)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Thin async wrappers over `ffprobe` and `ffmpeg`. Commands run without a shell.

`concat_copy` joins files with the concat demuxer and `-c copy`: a remux, never a re-encode. It refuses to try
when the segments' streams differ in codec, pixel format, size or frame rate.
"""

from __future__ import annotations

import asyncio
import json
import os
from functools import partial
from pathlib import Path

import numpy as np
from anyio import to_thread
from pydantic import BaseModel, ConfigDict


class RemuxError(Exception):
    """ffprobe or ffmpeg failed, or the segments cannot be joined without re-encoding."""


class StreamInfo(BaseModel):
    """What ffprobe reports for the first video stream. `nb_read_packets` comes from `-count_packets`, which
    reads the whole file, because `nb_frames` is not reliable in every container."""

    model_config = ConfigDict(frozen=True)

    codec_name: str
    pix_fmt: str
    width: int
    height: int
    r_frame_rate: str
    avg_frame_rate: str
    nb_read_packets: int
    duration: float | None = None

    def join_key(self) -> tuple[str, str, int, int, str]:
        return (self.codec_name, self.pix_fmt, self.width, self.height, self.r_frame_rate)


async def _run(*cmd: str) -> bytes:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise RemuxError(f"{cmd[0]} exited {proc.returncode}: {err.decode(errors='replace').strip()[-400:]}")
    return out


async def probe(path: Path) -> StreamInfo:
    out = await _run(
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
        "-show_entries",
        "stream=codec_name,pix_fmt,width,height,r_frame_rate,avg_frame_rate,nb_read_packets,duration",
        "-of", "json", str(path),
    )  # fmt: skip
    streams = json.loads(out).get("streams", [])
    if not streams:
        raise RemuxError(f"{path.name}: no video stream")
    stream = streams[0]
    try:
        duration = float(stream["duration"])
    except (KeyError, ValueError):
        duration = None
    return StreamInfo(**{**stream, "nb_read_packets": int(stream["nb_read_packets"]), "duration": duration})


async def ffmpeg_version() -> str:
    first_line = (await _run("ffmpeg", "-version")).decode().splitlines()[0]
    return first_line.split()[2]


def _quote(path: Path) -> str:
    return "'" + str(path.resolve()).replace("'", "'\\''") + "'"


async def concat_copy(parts: list[Path], out: Path) -> None:
    """Join `parts` into `out` by lossless remux, via `<out>.part` so `out` is never half-made."""
    infos = [await probe(p) for p in parts]
    if len({i.join_key() for i in infos}) > 1:
        detail = "; ".join(f"{p.name}: {i.codec_name} {i.pix_fmt} {i.width}x{i.height} {i.r_frame_rate}"
                           for p, i in zip(parts, infos, strict=True))  # fmt: skip
        raise RemuxError(f"segments differ in codec, pixel format, size or frame rate ({detail})")
    await to_thread.run_sync(partial(out.parent.mkdir, parents=True, exist_ok=True))
    listing = out.with_name(out.name + ".concat.txt")
    part = out.with_name(out.name + ".part")
    await to_thread.run_sync(listing.write_text, "".join(f"file {_quote(p)}\n" for p in parts))
    try:
        await _run(
            "ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
            "-c", "copy", "-movflags", "+faststart", "-f", "mp4", str(part),
        )  # fmt: skip
        await to_thread.run_sync(os.replace, part, out)
    finally:
        await to_thread.run_sync(partial(listing.unlink, missing_ok=True))
        await to_thread.run_sync(partial(part.unlink, missing_ok=True))


async def sample_frames(path: Path, total: int, info: StreamInfo, max_width: int = 150) -> np.ndarray:
    """Decode about `min(total, 100..10000)` evenly spaced frames from the first `total` frames, downscaled to
    at most `max_width` pixels wide. Returns uint8 RGB, shape `(count, height, width, 3)`.

    The sample size follows the heuristic LeRobot uses for its image statistics (100 frames minimum, growing
    with length to a cap). Only the stats read these frames; the exported video is never re-encoded."""
    wanted = total if total < 100 else max(100, min(int(total**0.75), 10_000))
    step = max(1, total // wanted)
    width = min(info.width, max_width)
    height = max(1, round(info.height * width / info.width))
    scale = f",scale={width}:{height}" if width != info.width else ""
    out = await _run(
        "ffmpeg", "-v", "error", "-i", str(path),
        "-vf", f"select='lt(n\\,{total})*not(mod(n\\,{step}))'{scale}",
        "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    )  # fmt: skip
    frame_bytes = width * height * 3
    if not out or len(out) % frame_bytes:
        raise RemuxError(f"{path.name}: could not decode frames for statistics")
    return np.frombuffer(out, dtype=np.uint8).reshape(-1, height, width, 3)

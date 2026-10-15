"""Export a packaged episode as a LeRobotDataset v3.0 directory, keeping Pearl's H.264 as it is.

The layout mirrors what `lerobot` 0.6.1 writes (`lerobot/datasets/utils.py`, `dataset_metadata.py`):
`meta/info.json`, `meta/stats.json`, `meta/tasks.parquet`, `meta/episodes/chunk-000/file-000.parquet`,
`data/chunk-000/file-000.parquet` and `videos/<key>/chunk-000/file-000.mp4`. It is written directly with
pyarrow and pandas. LeRobot's own recording path decodes frames and re-encodes them, which this export
avoids on purpose.

Pearl records video only, so there is no `action` or `observation.state`: those columns stay absent until a
lab joins its own step table. The step table is indexed by frame number and `timestamp = frame_index / fps`;
this says nothing about timing between cameras. `video.*` values are probed from the files, never assumed.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from anyio import to_thread

from pearl_episodes import __version__
from pearl_episodes.episodes.manifest import (
    Derived,
    Incident,
    load_manifest,
    sha256_of_async,
)
from pearl_episodes.episodes.packager import package
from pearl_episodes.media.ffmpeg import StreamInfo, probe, sample_frames

CODEBASE_VERSION = "v3.0"
KEY_PREFIX = "observation.images."
CHUNK_FILE = "chunk-000/file-000"
DATA_PATH = "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet"
VIDEO_PATH = "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4"
QUANTILES = {"q01": 0.01, "q10": 0.10, "q50": 0.50, "q90": 0.90, "q99": 0.99}
DEFAULT_FEATURES = {
    "timestamp": ("float32", pa.float32()),
    "frame_index": ("int64", pa.int64()),
    "episode_index": ("int64", pa.int64()),
    "index": ("int64", pa.int64()),
    "task_index": ("int64", pa.int64()),
}


class ExportError(Exception):
    """The episode cannot be exported as one LeRobot episode without guessing."""


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not slug:
        raise ExportError(f"camera name {name!r} has no letters or digits to build a feature key from")
    return slug


def _integer_fps(info: StreamInfo) -> int:
    rate = Fraction(info.r_frame_rate)
    if rate.denominator != 1:
        raise ExportError(
            f"frame rate {info.r_frame_rate} is not an integer; LeRobot stores fps as an integer"
        )
    return int(rate)


def _vector_stats(values: np.ndarray) -> dict[str, list[float] | list[int]]:
    stats: dict[str, Any] = {
        "min": [float(values.min())],
        "max": [float(values.max())],
        "mean": [float(values.mean())],
        "std": [float(values.std())],
        "count": [int(values.size)],
    }
    stats.update({name: [float(np.quantile(values, q))] for name, q in QUANTILES.items()})
    return stats


def _image_stats(frames: np.ndarray) -> dict[str, Any]:
    """Per-channel stats over sampled frames, scaled to [0, 1], shape (3, 1, 1) like LeRobot's."""
    pixels = frames.astype(np.float32).transpose(3, 0, 1, 2).reshape(3, -1) / 255.0

    def column(values: np.ndarray) -> list[list[list[float]]]:
        return [[[float(v)]] for v in values]

    stats: dict[str, Any] = {
        "min": column(pixels.min(axis=1)),
        "max": column(pixels.max(axis=1)),
        "mean": column(pixels.mean(axis=1)),
        "std": column(pixels.std(axis=1)),
        "count": [int(frames.shape[0])],
    }
    stats.update({name: column(np.quantile(pixels, q, axis=1)) for name, q in QUANTILES.items()})
    return stats


def _write_tables(
    root: Path,
    length: int,
    task: str,
    keys: dict[str, StreamInfo],
    fps: int,
    stats: dict[str, Any],
) -> None:
    """Write the step table, tasks and the episode metadata row under `root`."""
    columns = {
        "timestamp": np.arange(length, dtype=np.float32) / np.float32(fps),
        "frame_index": np.arange(length, dtype=np.int64),
        "episode_index": np.zeros(length, dtype=np.int64),
        "index": np.arange(length, dtype=np.int64),
        "task_index": np.zeros(length, dtype=np.int64),
    }
    schema = pa.schema([(name, kind) for name, (_, kind) in DEFAULT_FEATURES.items()])
    data_file = root / DATA_PATH.format(chunk_index=0, file_index=0)
    data_file.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table(columns, schema=schema), data_file)

    tasks = pd.DataFrame({"task_index": [0]}, index=pd.Index([task], name="task"))
    tasks.to_parquet(root / "meta" / "tasks.parquet")

    row: dict[str, Any] = {"episode_index": 0, "tasks": [task], "length": length}
    row.update({"data/chunk_index": 0, "data/file_index": 0})
    row.update({"dataset_from_index": 0, "dataset_to_index": length})
    for key, info in keys.items():
        row[f"videos/{key}/chunk_index"] = 0
        row[f"videos/{key}/file_index"] = 0
        row[f"videos/{key}/from_timestamp"] = 0.0
        row[f"videos/{key}/to_timestamp"] = (
            info.duration if info.duration is not None else info.nb_read_packets / fps
        )
    row.update({"meta/episodes/chunk_index": 0, "meta/episodes/file_index": 0})
    for feature, feature_stats in stats.items():
        row.update({f"stats/{feature}/{name}": value for name, value in feature_stats.items()})
    episodes_file = root / "meta" / "episodes" / "chunk-000" / "file-000.parquet"
    episodes_file.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist([row]), episodes_file)


async def export_lerobot_v3(episode_dir: Path) -> Path:
    """Write `<episode_dir>/lerobot` from a packaged episode, update the manifest's `derived[]` and
    `hashes.txt`, and return the LeRobot directory. Never overwrites an existing export."""
    final = episode_dir / "lerobot"
    if final.exists():
        raise FileExistsError(f"{final} already exists; exports are never overwritten")
    manifest = await to_thread.run_sync(load_manifest, episode_dir / "manifest.json")
    joined = {d.path for d in manifest.derived}

    cameras: dict[str, tuple[Path, StreamInfo, str]] = {}
    for camera in manifest.cameras:
        relative = f"joined/{camera.channel_id}.mp4"
        if relative not in joined or not (episode_dir / relative).exists():
            raise ExportError(f"no joined video for channel {camera.channel_id}; package the take first")
        key = KEY_PREFIX + _slug(camera.channel_name)
        if key in cameras:
            raise ExportError(
                f"cameras {cameras[key][2]!r} and {camera.channel_name!r} make the same key {key}"
            )
        cameras[key] = (episode_dir / relative, await probe(episode_dir / relative), camera.channel_name)

    rates = {_integer_fps(info) for _, info, _ in cameras.values()}
    if len(rates) > 1:
        detail = ", ".join(f"{name}: {info.r_frame_rate}" for _, info, name in cameras.values())
        raise ExportError(f"cameras have different frame rate ({detail}); LeRobot has one fps per dataset")
    fps = rates.pop()
    length = min(info.nb_read_packets for _, info, _ in cameras.values())

    incidents: list[Incident] = []
    now = datetime.now(UTC).isoformat(timespec="seconds")
    counts = {name: info.nb_read_packets for _, info, name in cameras.values()}
    if len(set(counts.values())) > 1:
        text = (
            f"frame counts differ between cameras ({', '.join(f'{n}: {c}' for n, c in counts.items())}); "
            f"the step table has {length} rows, the shortest, and each video is kept in full"
        )
        incidents.append(Incident(ts=now, source="pearl-episodes", text=text))
    for _, info, name in cameras.values():
        if info.r_frame_rate != info.avg_frame_rate:
            text = (
                f"{name}: r_frame_rate {info.r_frame_rate} differs from avg_frame_rate {info.avg_frame_rate}"
            )
            incidents.append(Incident(ts=now, source="pearl-episodes", text=text))

    features: dict[str, Any] = {
        key: {
            "dtype": "video",
            "shape": [info.height, info.width, 3],
            "names": ["height", "width", "channels"],
            "info": {
                "video.height": info.height,
                "video.width": info.width,
                "video.codec": info.codec_name,
                "video.pix_fmt": info.pix_fmt,
                "video.fps": fps,
                "video.channels": 3,
                "is_depth_map": False,
            },
        }
        for key, (_, info, _) in cameras.items()
    }
    features.update({n: {"dtype": d, "shape": [1], "names": None} for n, (d, _) in DEFAULT_FEATURES.items()})

    stats: dict[str, Any] = {}
    for key, (path, info, _) in cameras.items():
        stats[key] = _image_stats(await sample_frames(path, length, info))
    scalars = {
        "timestamp": np.arange(length, dtype=np.float32) / np.float32(fps),
        "frame_index": np.arange(length, dtype=np.float64),
        "episode_index": np.zeros(length),
        "index": np.arange(length, dtype=np.float64),
        "task_index": np.zeros(length),
    }
    stats.update({name: _vector_stats(values) for name, values in scalars.items()})

    task = manifest.task_label or "unlabeled"
    info_json = {
        "codebase_version": CODEBASE_VERSION,
        "fps": fps,
        "features": features,
        "total_episodes": 1,
        "total_frames": length,
        "total_tasks": 1,
        "chunks_size": 1000,
        "data_files_size_in_mb": 100,
        "video_files_size_in_mb": 200,
        "data_path": DATA_PATH,
        "video_path": VIDEO_PATH,
        "robot_type": None,
        "splits": {"train": "0:1"},
    }
    staging = episode_dir / ".lerobot.building"
    await to_thread.run_sync(shutil.rmtree, staging, True)
    try:
        derived = await _write_export(staging, info_json, stats, cameras, task, length, fps)
        await to_thread.run_sync(staging.rename, final)
    except BaseException:
        await to_thread.run_sync(shutil.rmtree, staging, True)
        raise
    updated = manifest.model_copy(
        update={"derived": [*manifest.derived, *derived], "incidents": [*manifest.incidents, *incidents]}
    )
    await package(updated, episode_dir)
    return final


async def _write_export(
    root: Path,
    info_json: dict[str, Any],
    stats: dict[str, Any],
    cameras: dict[str, tuple[Path, StreamInfo, str]],
    task: str,
    length: int,
    fps: int,
) -> list[Derived]:
    """Write every file of the export under `root`; return its `Derived` entries (paths start `lerobot/`)."""
    infos = {key: info for key, (_, info, _) in cameras.items()}

    def write_all() -> None:
        (root / "meta").mkdir(parents=True)
        (root / "meta" / "info.json").write_text(json.dumps(info_json, indent=2))
        (root / "meta" / "stats.json").write_text(json.dumps(stats, indent=2))
        _write_tables(root, length, task, infos, fps, stats)
        for key, (source, _, _) in cameras.items():
            dest = root / VIDEO_PATH.format(video_key=key, chunk_index=0, file_index=0)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)

    def list_files() -> list[Path]:
        return sorted(p for p in root.rglob("*") if p.is_file())

    await to_thread.run_sync(write_all)
    files = await to_thread.run_sync(list_files)
    return [
        Derived(
            path=f"lerobot/{p.relative_to(root).as_posix()}",
            sha256=await sha256_of_async(p),
            tool="pearl-episodes",
            version=__version__,
        )
        for p in files
    ]

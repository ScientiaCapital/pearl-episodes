"""LeRobot v3.0 export (issue #8): Pearl's H.264 is copied, never re-encoded; metadata is probed."""

import json
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from pearl_episodes.episodes.manifest import load_manifest
from pearl_episodes.episodes.packager import CameraInput, TakeLabels, package_take
from pearl_episodes.export.lerobot_v3 import ExportError, export_lerobot_v3
from tests.conftest import make_mp4, make_pulled_folder, needs_ffmpeg

pytestmark = needs_ffmpeg

LABELS = TakeLabels(
    device_serial="TEST-SERIAL-0001", device_model="Pearl Mini", firmware="4.24.6", task_label="pick cup"
)
KEY = "observation.images.wide_cam"


async def _episode(tmp_path: Path, *specs: tuple[str, str, int, int | str]) -> Path:
    """Package a take with one generated clip per `(channel_id, name, frames, rate)` spec."""
    cameras = []
    for n, (channel_id, name, frames, rate) in enumerate(specs):
        clip = make_mp4(tmp_path / "gen" / f"{channel_id}.mp4", frames=frames, rate=rate)
        folder = make_pulled_folder(
            tmp_path / "rec" / channel_id, {"1": clip}, {"1": f"2026-12-11T17:32:1{n}"}
        )
        cameras.append(CameraInput(channel_id, name, channel_id, folder, ["1"]))
    [episode] = await package_take(cameras, LABELS, tmp_path / "episodes", episode_id="ep-0001")
    return episode


async def test_export_writes_the_v3_layout_and_info(tmp_path: Path) -> None:
    episode = await _episode(tmp_path, ("1", "Wide Cam", 10, 10))
    lerobot = await export_lerobot_v3(episode)
    assert lerobot == episode / "lerobot"
    info = json.loads((lerobot / "meta" / "info.json").read_text())
    assert (info["codebase_version"], info["fps"], info["total_episodes"], info["total_frames"]) == (
        "v3.0", 10, 1, 10,
    )  # fmt: skip
    assert (info["total_tasks"], info["splits"], info["robot_type"]) == (1, {"train": "0:1"}, None)
    assert info["data_path"] == "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet"
    assert info["video_path"] == "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4"
    video = info["features"][KEY]
    assert (video["dtype"], video["shape"], video["names"]) == (
        "video",
        [36, 64, 3],
        ["height", "width", "channels"],
    )
    assert video["info"] == {
        "video.height": 36, "video.width": 64, "video.codec": "h264", "video.pix_fmt": "yuv420p",
        "video.fps": 10, "video.channels": 3, "is_depth_map": False,
    }  # fmt: skip
    for name in ("timestamp", "frame_index", "episode_index", "index", "task_index"):
        assert info["features"][name]["shape"] == [1] and info["features"][name]["names"] is None
    assert not any(k in info["features"] for k in ("action", "observation.state"))


async def test_the_pearl_video_is_copied_byte_for_byte(tmp_path: Path) -> None:
    episode = await _episode(tmp_path, ("1", "Wide Cam", 10, 10))
    lerobot = await export_lerobot_v3(episode)
    exported = lerobot / "videos" / KEY / "chunk-000" / "file-000.mp4"
    assert exported.read_bytes() == (episode / "joined" / "1.mp4").read_bytes()


async def test_step_table_has_one_row_per_frame_with_timestamp_from_fps(tmp_path: Path) -> None:
    lerobot = await export_lerobot_v3(await _episode(tmp_path, ("1", "Wide Cam", 10, 10)))
    table = pq.read_table(lerobot / "data" / "chunk-000" / "file-000.parquet")
    assert table.column_names == ["timestamp", "frame_index", "episode_index", "index", "task_index"]
    assert [str(t) for t in table.schema.types] == ["float", "int64", "int64", "int64", "int64"]
    rows = table.to_pydict()
    assert rows["frame_index"] == list(range(10)) and rows["index"] == list(range(10))
    assert rows["timestamp"] == pytest.approx([i / 10 for i in range(10)])
    assert set(rows["episode_index"]) == {0} and set(rows["task_index"]) == {0}


async def test_tasks_and_episode_metadata(tmp_path: Path) -> None:
    lerobot = await export_lerobot_v3(await _episode(tmp_path, ("1", "Wide Cam", 10, 10)))
    tasks = pd.read_parquet(lerobot / "meta" / "tasks.parquet")
    assert (
        tasks.index.name == "task" and list(tasks.index) == ["pick cup"] and list(tasks["task_index"]) == [0]
    )
    [row] = pq.read_table(lerobot / "meta" / "episodes" / "chunk-000" / "file-000.parquet").to_pylist()
    assert (row["episode_index"], row["tasks"], row["length"]) == (0, ["pick cup"], 10)
    assert (row["dataset_from_index"], row["dataset_to_index"]) == (0, 10)
    assert (row["data/chunk_index"], row["data/file_index"]) == (0, 0)
    assert (row["meta/episodes/chunk_index"], row["meta/episodes/file_index"]) == (0, 0)
    assert (row[f"videos/{KEY}/chunk_index"], row[f"videos/{KEY}/file_index"]) == (0, 0)
    assert row[f"videos/{KEY}/from_timestamp"] == 0.0
    assert row[f"videos/{KEY}/to_timestamp"] == pytest.approx(1.0, abs=0.15)
    assert f"stats/{KEY}/mean" in row and "stats/timestamp/max" in row


async def test_stats_for_video_are_per_channel_in_0_to_1(tmp_path: Path) -> None:
    lerobot = await export_lerobot_v3(await _episode(tmp_path, ("1", "Wide Cam", 10, 10)))
    stats = json.loads((lerobot / "meta" / "stats.json").read_text())
    video = stats[KEY]
    assert set(video) == {"min", "max", "mean", "std", "count", "q01", "q10", "q50", "q90", "q99"}
    assert len(video["mean"]) == 3 and len(video["mean"][0]) == 1 and len(video["mean"][0][0]) == 1
    assert all(0.0 <= c[0][0] <= 1.0 for c in video["mean"]) and video["count"] == [10]
    assert stats["timestamp"]["min"] == [0.0] and stats["timestamp"]["max"] == pytest.approx([0.9])
    assert stats["frame_index"]["max"] == [9.0] and stats["frame_index"]["count"] == [10]


async def test_export_is_recorded_in_the_manifest_and_hashes(tmp_path: Path) -> None:
    episode = await _episode(tmp_path, ("1", "Wide Cam", 10, 10))
    await export_lerobot_v3(episode)
    manifest = load_manifest(episode / "manifest.json")
    paths = {d.path for d in manifest.derived}
    assert {"joined/1.mp4", "lerobot/meta/info.json", f"lerobot/videos/{KEY}/chunk-000/file-000.mp4"} <= paths
    assert all(d.tool == "pearl-episodes" for d in manifest.derived if d.path.startswith("lerobot/"))
    if shutil.which("shasum"):
        subprocess.run(
            ["shasum", "-a", "256", "-c", "hashes.txt"], cwd=episode, check=True, capture_output=True
        )


async def test_cameras_with_different_frame_counts_use_the_shortest_and_say_so(tmp_path: Path) -> None:
    episode = await _episode(tmp_path, ("1", "Wide Cam", 10, 10), ("2", "Side Cam", 12, 10))
    lerobot = await export_lerobot_v3(episode)
    info = json.loads((lerobot / "meta" / "info.json").read_text())
    assert info["total_frames"] == 10 and "observation.images.side_cam" in info["features"]
    [incident] = load_manifest(episode / "manifest.json").incidents
    assert incident.source == "pearl-episodes" and "frame counts differ" in incident.text


async def test_cameras_with_different_frame_rates_are_refused(tmp_path: Path) -> None:
    episode = await _episode(tmp_path, ("1", "Wide Cam", 10, 10), ("2", "Side Cam", 10, 20))
    with pytest.raises(ExportError, match="frame rate"):
        await export_lerobot_v3(episode)
    assert not (episode / "lerobot").exists()


async def test_a_non_integer_frame_rate_is_refused(tmp_path: Path) -> None:
    episode = await _episode(tmp_path, ("1", "Wide Cam", 10, "30000/1001"))
    with pytest.raises(ExportError, match="integer"):
        await export_lerobot_v3(episode)


async def test_camera_names_that_make_the_same_key_are_refused(tmp_path: Path) -> None:
    episode = await _episode(tmp_path, ("1", "Wide Cam", 10, 10), ("2", "wide-cam", 10, 10))
    with pytest.raises(ExportError, match="same key"):
        await export_lerobot_v3(episode)


async def test_an_existing_export_is_never_overwritten(tmp_path: Path) -> None:
    episode = await _episode(tmp_path, ("1", "Wide Cam", 10, 10))
    await export_lerobot_v3(episode)
    with pytest.raises(FileExistsError):
        await export_lerobot_v3(episode)

"""The export opens with LeRobot's own loader (issue #8). Needs the datasets extra; skipped without it."""

import importlib.util
from pathlib import Path

import pytest

from pearl_episodes.episodes.packager import CameraInput, TakeLabels, package_take
from pearl_episodes.export.lerobot_v3 import export_lerobot_v3
from tests.conftest import make_mp4, make_pulled_folder, needs_ffmpeg

pytestmark = [
    pytest.mark.datasets,
    needs_ffmpeg,
    pytest.mark.skipif(importlib.util.find_spec("lerobot") is None, reason="lerobot is not installed"),
]


async def test_lerobot_opens_the_export_and_decodes_first_and_last_frames(tmp_path: Path) -> None:
    from lerobot.datasets import LeRobotDataset

    clip = make_mp4(tmp_path / "gen" / "1.mp4", frames=10, size="64x36", rate=10)
    folder = make_pulled_folder(tmp_path / "rec" / "1", {"1": clip}, {"1": "2026-12-11T17:32:10"})
    labels = TakeLabels("TEST-SERIAL-0001", "Pearl Mini", "4.24.6", task_label="pick cup")
    [episode] = await package_take(
        [CameraInput("1", "Wide Cam", "1", folder, ["1"])],
        labels,
        tmp_path / "episodes",
        episode_id="ep-0001",
    )
    lerobot = await export_lerobot_v3(episode)

    dataset = LeRobotDataset("pearl/test", root=lerobot, video_backend="pyav")
    assert len(dataset) == 10 and dataset.fps == 10 and dataset.meta.total_episodes == 1
    assert dataset.meta.video_keys == ["observation.images.wide_cam"]
    assert dataset.meta.info.features["observation.images.wide_cam"]["info"]["video.codec"] == "h264"
    first, last = dataset[0], dataset[9]
    assert tuple(first["observation.images.wide_cam"].shape) == (3, 36, 64)
    assert tuple(last["observation.images.wide_cam"].shape) == (3, 36, 64)
    assert first["task"] == "pick cup" and int(last["frame_index"]) == 9

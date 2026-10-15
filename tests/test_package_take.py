"""`package_take` (issue #7): originals kept, joined video per camera by remux, sub-episodes on failure."""

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from pearl_episodes.episodes.manifest import load_manifest, sha256_of
from pearl_episodes.episodes.packager import CameraInput, TakeLabels, package_take
from pearl_episodes.media.ffmpeg import probe
from tests.conftest import make_mp4, make_pulled_folder, needs_ffmpeg

pytestmark = needs_ffmpeg

LABELS = TakeLabels(
    device_serial="TEST-SERIAL-0001",
    device_model="Pearl Mini",
    firmware="4.24.6",
    task_label="pick cup",
    operator="tim",
    clock_source="unknown",
)


def _verify_hashes(episode: Path) -> None:
    for line in (episode / "hashes.txt").read_text().splitlines():
        digest, rel = line.split("  ", 1)
        assert hashlib.sha256((episode / rel).read_bytes()).hexdigest() == digest


async def test_one_segment_take_has_original_joined_video_manifest_and_hashes(tmp_path: Path) -> None:
    folder = make_pulled_folder(
        tmp_path / "rec" / "1", {"7": make_mp4(tmp_path / "gen" / "7.mp4")}, {"7": "2026-12-11T17:32:10"}
    )
    camera = CameraInput("1", "Wide Cam", "1", folder, ["7"])
    [episode] = await package_take([camera], LABELS, tmp_path / "episodes")
    assert episode.name == "TEST-SERIAL-0001-2026-12-11T17-32-10"
    manifest = load_manifest(episode / "manifest.json")
    [cam] = manifest.cameras
    [segment] = cam.segments
    assert segment.path == "source/1/7.mp4" and segment.sha256 == sha256_of(tmp_path / "gen" / "7.mp4")
    assert (episode / segment.path).read_bytes() == (tmp_path / "gen" / "7.mp4").read_bytes()
    [derived] = manifest.derived
    assert (derived.path, derived.tool) == ("joined/1.mp4", "ffmpeg")
    assert (await probe(episode / derived.path)).nb_read_packets == 10
    assert manifest.start_time == "2026-12-11T17:32:10" and manifest.task_label == "pick cup"
    assert "without losing any content" not in manifest.notes
    _verify_hashes(episode)
    if shutil.which("shasum"):
        subprocess.run(
            ["shasum", "-a", "256", "-c", "hashes.txt"], cwd=episode, check=True, capture_output=True
        )


async def test_three_segment_take_is_ordered_by_created_then_id_and_joined(tmp_path: Path) -> None:
    clips = {fid: make_mp4(tmp_path / "gen" / f"{fid}.mp4") for fid in ("9", "10", "11")}
    created = {"9": "2026-12-11T17:32:10", "10": "2026-12-11T17:02:10", "11": "2026-12-11T17:32:10"}
    folder = make_pulled_folder(tmp_path / "rec" / "1", clips, created)
    camera = CameraInput("1", "Wide Cam", "1", folder, ["11", "9", "10"])
    [episode] = await package_take([camera], LABELS, tmp_path / "episodes", episode_id="ep-0001")
    manifest = load_manifest(episode / "manifest.json")
    [cam] = manifest.cameras
    assert [(s.seq, s.file_id) for s in cam.segments] == [(0, "10"), (1, "11"), (2, "9")]
    assert (await probe(episode / "joined" / "1.mp4")).nb_read_packets == 30
    assert "without losing any content" in manifest.notes and "pearl-family/about-recording" in manifest.notes
    _verify_hashes(episode)


async def test_two_cameras_get_one_joined_video_each(tmp_path: Path) -> None:
    wide = make_pulled_folder(
        tmp_path / "rec" / "1", {"1": make_mp4(tmp_path / "gen" / "w.mp4")}, {"1": "2026-12-11T17:32:10"}
    )
    side = make_pulled_folder(
        tmp_path / "rec" / "2", {"5": make_mp4(tmp_path / "gen" / "s.mp4")}, {"5": "2026-12-11T17:32:11"}
    )
    cameras = [CameraInput("1", "Wide Cam", "1", wide, ["1"]), CameraInput("2", "Side Cam", "2", side, ["5"])]
    [episode] = await package_take(cameras, LABELS, tmp_path / "episodes", episode_id="ep-0001")
    manifest = load_manifest(episode / "manifest.json")
    assert [c.channel_name for c in manifest.cameras] == ["Wide Cam", "Side Cam"]
    assert sorted(d.path for d in manifest.derived) == ["joined/1.mp4", "joined/2.mp4"]
    _verify_hashes(episode)


async def test_segments_that_cannot_be_remuxed_become_sub_episodes_with_the_reason(tmp_path: Path) -> None:
    clips = {
        "1": make_mp4(tmp_path / "gen" / "1.mp4", size="64x36"),
        "2": make_mp4(tmp_path / "gen" / "2.mp4", size="96x54"),
    }
    folder = make_pulled_folder(
        tmp_path / "rec" / "1", clips, {"1": "2026-12-11T17:02:10", "2": "2026-12-11T17:32:10"}
    )
    camera = CameraInput("1", "Wide Cam", "1", folder, ["1", "2"])
    episodes = await package_take([camera], LABELS, tmp_path / "episodes", episode_id="ep-0001")
    assert [e.name for e in episodes] == ["ep-0001-part00", "ep-0001-part01"]
    for number, episode in enumerate(episodes):
        manifest = load_manifest(episode / "manifest.json")
        [cam] = manifest.cameras
        [segment] = cam.segments
        assert (segment.seq, segment.file_id) == (0, str(number + 1))
        [incident] = manifest.incidents
        assert incident.source == "pearl-episodes" and "differ" in incident.text
        assert "2 sub-episodes" in manifest.notes
        _verify_hashes(episode)


async def test_a_copied_original_that_differs_from_the_index_hash_is_refused(tmp_path: Path) -> None:
    folder = make_pulled_folder(
        tmp_path / "rec" / "1", {"7": make_mp4(tmp_path / "gen" / "7.mp4")}, {"7": "2026-12-11T17:32:10"}
    )
    (folder / "7.mp4").write_bytes(b"corrupted after the pull")
    with pytest.raises(ValueError, match="hash"):
        await package_take([CameraInput("1", "Wide Cam", "1", folder, ["7"])], LABELS, tmp_path / "episodes")
    assert not (tmp_path / "episodes").exists() or list((tmp_path / "episodes").rglob("manifest.json")) == []


async def test_an_id_that_was_never_pulled_is_refused(tmp_path: Path) -> None:
    folder = make_pulled_folder(
        tmp_path / "rec" / "1", {"7": make_mp4(tmp_path / "gen" / "7.mp4")}, {"7": "2026-12-11T17:32:10"}
    )
    with pytest.raises(ValueError, match="not pulled"):
        await package_take(
            [CameraInput("1", "Wide Cam", "1", folder, ["7", "8"])], LABELS, tmp_path / "episodes"
        )

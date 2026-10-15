from datetime import UTC, datetime
from pathlib import Path

from pearl_episodes.episodes.manifest import EpisodeManifest, sha256_of
from pearl_episodes.episodes.packager import camera_file_from, package


async def test_manifest_roundtrip_and_hashes(tmp_path: Path) -> None:
    video = tmp_path / "Wide_Cam_Oct14_17-32-30.mp4"
    video.write_bytes(b"not really video")
    cam = camera_file_from(video, channel_id="1", channel_name="Wide Cam", duration_s=12.5)
    assert cam.sha256 == sha256_of(video)
    manifest = EpisodeManifest(
        episode_id="ep-0001",
        device_serial="TEST-SERIAL-0001",
        device_model="Pearl-2",
        firmware="4.24.6",
        start_time=datetime(2026, 10, 14, 17, 32, 30, tzinfo=UTC),
        cameras=[cam],
        task_label="pick cup",
        operator="tim",
        clock_source="ntp",
    )
    out = await package(manifest, tmp_path / "ep-0001")
    loaded = EpisodeManifest.model_validate_json((out / "manifest.json").read_text())
    assert loaded == manifest
    assert (out / "hashes.txt").read_text().startswith(cam.sha256)
    assert sorted(p.name for p in out.iterdir()) == ["hashes.txt", "manifest.json"]

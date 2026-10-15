"""Manifest v2 (issue #6): ordered segments, derived files, incidents; frozen, validated; v1 still loads."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from pearl_episodes.episodes.manifest import (
    Camera,
    Derived,
    EpisodeManifest,
    Incident,
    Segment,
    load_manifest,
    sha256_of,
)
from pearl_episodes.episodes.packager import package

SHA_A = "a" * 64
SHA_B = "b" * 64


def _segment(seq: int, file_id: str = "7", sha256: str = SHA_A) -> Segment:
    return Segment(
        seq=seq,
        file_id=file_id,
        path=f"source/1/{file_id}.mp4",
        created="2026-12-11T17:32:30",
        duration=60,
        size=3,
        sha256=sha256,
        recorder_id="1",
        event_id=None,
    )


def _manifest(**overrides: object) -> EpisodeManifest:
    fields: dict[str, object] = {
        "episode_id": "ep-0001",
        "device_serial": "TEST-SERIAL-0001",
        "device_model": "Pearl Mini",
        "firmware": "4.24.6",
        "start_time": "2026-12-11T17:32:30",
        "cameras": [Camera(channel_id="1", channel_name="Wide Cam", segments=[_segment(0)])],
        "task_label": "pick cup",
        "operator": "tim",
        "clock_source": "manual",
    }
    return EpisodeManifest(**{**fields, **overrides})  # type: ignore[arg-type]


def test_v2_roundtrips_through_json() -> None:
    manifest = _manifest(
        derived=[Derived(path="lerobot/videos/wide_cam.mp4", sha256=SHA_B, tool="ffmpeg", version="9.0.2")],
        incidents=[
            Incident(ts="2026-12-11T17:40:00", source="get_system_status_for_devices", text="Low storage")
        ],
        session_id="session-0001",
    )
    assert manifest.schema_version == 2
    assert EpisodeManifest.model_validate_json(manifest.model_dump_json()) == manifest


def test_manifest_is_frozen_and_rejects_unknown_fields() -> None:
    manifest = _manifest()
    with pytest.raises(ValidationError):
        manifest.task_label = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        _manifest(frame_rate=30)


@pytest.mark.parametrize("seqs", [[1], [0, 2], [1, 0], [0, 0]])
def test_segments_must_be_numbered_0_to_n_minus_1_in_order(seqs: list[int]) -> None:
    with pytest.raises(ValidationError):
        Camera(
            channel_id="1",
            channel_name="Wide Cam",
            segments=[_segment(s, file_id=str(i)) for i, s in enumerate(seqs)],
        )


def test_a_camera_needs_at_least_one_segment() -> None:
    with pytest.raises(ValidationError):
        Camera(channel_id="1", channel_name="Wide Cam", segments=[])


@pytest.mark.parametrize("bad", ["A" * 64, "a" * 63, "g" * 64, ""])
def test_sha256_must_be_64_lowercase_hex_characters(bad: str) -> None:
    with pytest.raises(ValidationError):
        _segment(0, sha256=bad)


@pytest.mark.parametrize("bad", ["../escape.mp4", "/abs/path.mp4", "", "a//b.mp4", "a/./b.mp4"])
def test_paths_must_be_safe_and_relative(bad: str) -> None:
    with pytest.raises(ValidationError):
        Derived(path=bad, sha256=SHA_B, tool="ffmpeg", version="9.0.2")


def test_clock_source_accepts_manual_and_rejects_anything_else() -> None:
    assert _manifest(clock_source="manual").clock_source == "manual"
    with pytest.raises(ValidationError):
        _manifest(clock_source="gps")


def test_load_manifest_upgrades_a_v1_file(tmp_path: Path) -> None:
    v1 = {
        "episode_id": "ep-0001",
        "device_serial": "TEST-SERIAL-0001",
        "device_model": "Pearl-2",
        "firmware": "4.24.6",
        "start_time": "2026-10-14T17:32:30Z",
        "cameras": [
            {
                "channel_id": "1",
                "channel_name": "Wide Cam",
                "file_name": "Wide_Cam_Oct14_17-32-30.mp4",
                "file_size": 16,
                "sha256": SHA_A,
                "duration_s": 12.5,
            }
        ],
        "task_label": "pick cup",
        "operator": "tim",
        "scene": "",
        "clock_source": "ntp",
        "notes": "",
        "schema_version": 1,
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(v1))
    loaded = load_manifest(path)
    assert loaded.schema_version == 2
    assert loaded.start_time == "2026-10-14T17:32:30Z"
    [camera] = loaded.cameras
    [segment] = camera.segments
    assert (segment.seq, segment.file_id, segment.path, segment.size, segment.sha256) == (
        0,
        "Wide_Cam_Oct14_17-32-30.mp4",
        "Wide_Cam_Oct14_17-32-30.mp4",
        16,
        SHA_A,
    )
    assert segment.duration == 12
    assert loaded.derived == [] and loaded.incidents == [] and loaded.session_id is None


def test_load_manifest_reads_v2_as_is(tmp_path: Path) -> None:
    manifest = _manifest()
    path = tmp_path / "manifest.json"
    path.write_text(manifest.model_dump_json())
    assert load_manifest(path) == manifest


async def test_package_writes_hashes_for_every_source_and_derived_file(tmp_path: Path) -> None:
    out = tmp_path / "ep-0001"
    (out / "source" / "1").mkdir(parents=True)
    (out / "source" / "1" / "7.mp4").write_bytes(b"abc")
    (out / "lerobot").mkdir()
    (out / "lerobot" / "wide_cam.mp4").write_bytes(b"abcabc")
    sha_src = hashlib.sha256(b"abc").hexdigest()
    sha_der = hashlib.sha256(b"abcabc").hexdigest()
    manifest = _manifest(
        cameras=[Camera(channel_id="1", channel_name="Wide Cam", segments=[_segment(0, sha256=sha_src)])],
        derived=[Derived(path="lerobot/wide_cam.mp4", sha256=sha_der, tool="ffmpeg", version="9.0.2")],
    )
    await package(manifest, out)
    assert (out / "hashes.txt").read_text() == f"{sha_src}  source/1/7.mp4\n{sha_der}  lerobot/wide_cam.mp4\n"
    assert load_manifest(out / "manifest.json") == manifest
    assert sorted(p.name for p in out.iterdir()) == ["hashes.txt", "lerobot", "manifest.json", "source"]
    if shutil.which("shasum"):
        subprocess.run(["shasum", "-a", "256", "-c", "hashes.txt"], cwd=out, check=True, capture_output=True)


def test_sha256_of_known_values(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.write_bytes(b"")
    abc = tmp_path / "abc"
    abc.write_bytes(b"abc")
    assert sha256_of(empty) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert sha256_of(abc) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

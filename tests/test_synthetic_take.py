"""scripts/make_synthetic_take.py (issue #9): a two-camera take made of ffmpeg test patterns, packaged and
exported, so the notebook runs before any real Pearl take exists."""

import importlib.util
import json
from pathlib import Path

from pearl_episodes.episodes.manifest import load_manifest
from tests.conftest import needs_ffmpeg

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "make_synthetic_take.py"


def _module():
    spec = importlib.util.spec_from_file_location("make_synthetic_take", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@needs_ffmpeg
async def test_build_makes_a_packaged_and_exported_two_camera_episode(tmp_path: Path) -> None:
    lerobot = await _module().build(tmp_path, seconds=1, size="64x36", fps=10)
    assert lerobot.parent.parent == tmp_path / "episodes"
    info = json.loads((lerobot / "meta" / "info.json").read_text())
    assert (info["fps"], info["total_frames"]) == (10, 10)
    assert sorted(k for k in info["features"] if k.startswith("observation.images.")) == [
        "observation.images.side_cam",
        "observation.images.wide_cam",
    ]
    manifest = load_manifest(lerobot.parent / "manifest.json")
    assert manifest.device_serial == "TEST-SERIAL-0001" and "synthetic" in manifest.notes.lower()


def test_the_script_has_a_main_that_parses_arguments() -> None:
    assert callable(_module().main)

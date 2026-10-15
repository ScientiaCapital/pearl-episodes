"""scripts/codec_compare.sh (issue #11): the bench codec test commands, reproducible on any Pearl file."""

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import make_mp4, needs_ffmpeg

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "codec_compare.sh"


def _has_svtav1() -> bool:
    if shutil.which("ffmpeg") is None:
        return False
    out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    return "libsvtav1" in out


@needs_ffmpeg
@pytest.mark.skipif(not _has_svtav1(), reason="this ffmpeg has no libsvtav1 encoder")
def test_it_compares_remux_with_lerobots_default_and_prints_the_commands(tmp_path: Path) -> None:
    clip = make_mp4(tmp_path / "in.mp4", frames=30, size="320x180", rate=10)
    out = tmp_path / "out"
    result = subprocess.run(["bash", str(SCRIPT), str(clip), str(out)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    for text in ("-c copy", "libsvtav1", "-crf 30", "-g 2", "SSIM", "PSNR", "remux", "lerobot_default"):
        assert text in result.stdout, text
    assert (out / "remux.mp4").exists() and (out / "lerobot_default.mp4").exists()
    assert (out / "remux.mp4").stat().st_size > 0


def test_it_explains_usage_without_arguments() -> None:
    result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 2 and "usage" in result.stderr.lower()

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from pearl_episodes.episodes.manifest import sha256_of


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run every test from an empty folder with no PEARL_* variables, so a developer's .env never leaks in."""
    monkeypatch.chdir(tmp_path)
    for name in [n for n in os.environ if n.startswith("PEARL_")]:
        monkeypatch.delenv(name)


FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg and ffprobe are not installed")


def make_mp4(
    path: Path, *, frames: int = 10, size: str = "64x36", rate: int | str = 10, pix_fmt: str = "yuv420p"
) -> Path:
    """A tiny generated H.264 clip (ffmpeg test pattern). No real footage is ever used in tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size={size}:rate={rate}",
            "-frames:v",
            str(frames),
            "-c:v",
            "libx264",
            "-pix_fmt",
            pix_fmt,
            "-g",
            "5",
            str(path),
        ],
        check=True,
    )
    return path


def make_pulled_folder(folder: Path, clips: dict[str, Path], created: dict[str, str]) -> Path:
    """A recordings folder as `pull` leaves it: `<id>.mp4` files plus `index.jsonl`."""
    folder.mkdir(parents=True, exist_ok=True)
    lines = []
    for fid, clip in clips.items():
        shutil.copy(clip, folder / f"{fid}.mp4")
        lines.append(
            json.dumps(
                {
                    "id": fid,
                    "name": f"Cam_{fid}",
                    "extension": "mp4",
                    "created": created[fid],
                    "duration": 1,
                    "size": clip.stat().st_size,
                    "recorder": "1",
                    "event_id": None,
                    "sha256": sha256_of(clip),
                    "path": f"{fid}.mp4",
                }
            )
        )
    (folder / "index.jsonl").write_text("\n".join(lines) + "\n")
    return folder

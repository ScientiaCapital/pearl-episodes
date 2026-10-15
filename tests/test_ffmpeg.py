"""ffmpeg wrapper (issue #7): probe, lossless concat, version. Clips are generated test patterns."""

from pathlib import Path

import pytest

from pearl_episodes.media.ffmpeg import RemuxError, concat_copy, ffmpeg_version, probe
from tests.conftest import make_mp4, needs_ffmpeg

pytestmark = needs_ffmpeg


async def test_probe_reports_the_stream_facts(tmp_path: Path) -> None:
    info = await probe(make_mp4(tmp_path / "a.mp4", frames=10, size="64x36", rate=10))
    assert (info.codec_name, info.pix_fmt, info.width, info.height) == ("h264", "yuv420p", 64, 36)
    assert (info.r_frame_rate, info.nb_read_packets) == ("10/1", 10)


async def test_concat_copy_joins_segments_without_re_encoding(tmp_path: Path) -> None:
    parts = [make_mp4(tmp_path / f"{i}.mp4", frames=10) for i in range(3)]
    out = tmp_path / "out" / "joined.mp4"
    await concat_copy(parts, out)
    info = await probe(out)
    assert (info.codec_name, info.pix_fmt, info.width, info.height) == ("h264", "yuv420p", 64, 36)
    assert info.nb_read_packets == 30
    assert list(out.parent.iterdir()) == [out]


async def test_concat_copy_refuses_segments_whose_streams_differ(tmp_path: Path) -> None:
    parts = [make_mp4(tmp_path / "a.mp4", size="64x36"), make_mp4(tmp_path / "b.mp4", size="96x54")]
    out = tmp_path / "joined.mp4"
    with pytest.raises(RemuxError, match="differ"):
        await concat_copy(parts, out)
    assert not out.exists()


async def test_probe_of_a_file_that_is_not_media_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not video")
    with pytest.raises(RemuxError):
        await probe(bad)


async def test_ffmpeg_version_is_a_version_string() -> None:
    version = await ffmpeg_version()
    assert version[0].isdigit() or version.startswith("n")

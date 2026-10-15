"""`pull` (issue #5): idempotent on file id, atomic, skips files the device is still writing."""

import hashlib
import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from pearl_episodes.config import Settings
from pearl_episodes.episodes.pull import PullReport, load_index, pull
from pearl_episodes.pearl.client import PearlClient

CONTENT = {"1": b"first-file", "2": b"second-file"}


def _listing(**flags: dict[str, object]) -> list[dict[str, object]]:
    items = []
    for fid, data in CONTENT.items():
        item: dict[str, object] = {
            "id": fid,
            "name": f"Cam_Dec11_17-32-{fid}0",
            "extension": "mp4",
            "recording": False,
            "downloaded": False,
            "created": f"2026-12-11T17:32:{fid}0",
            "duration": 60,
            "size": len(data),
            "recorder": "1",
            "uploading": False,
            "event_id": None,
        }
        item.update(flags.get(fid, {}))
        items.append(item)
    return items


class Device:
    """A mocked Pearl: a listing, file bodies, and a count of download requests."""

    def __init__(self, listing: list[dict[str, object]], fail_on: str | None = None) -> None:
        self.listing = listing
        self.fail_on = fail_on
        self.downloads: list[str] = []

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path.endswith("/archive/files"):
                start = int(request.url.params["from"])
                return httpx.Response(200, json={"status": "ok", "result": self.listing[start:]})
            fid = path.rsplit("/", 1)[1]
            self.downloads.append(fid)

            async def body() -> AsyncIterator[bytes]:
                data = CONTENT[fid]
                yield data[:4]
                if fid == self.fail_on:
                    raise httpx.ReadError("connection dropped")
                yield data[4:]

            return httpx.Response(200, content=body(), headers={"Content-Length": str(len(CONTENT[fid]))})

        return httpx.MockTransport(handler)


def _client(device: Device) -> PearlClient:
    return PearlClient(Settings(host="pearl.test", password="x"), transport=device.transport())


async def test_pull_downloads_new_files_and_writes_an_index(tmp_path: Path) -> None:
    device = Device(_listing())
    async with _client(device) as client:
        report = await pull(client, "1", tmp_path / "pearl.test" / "1")
    assert report == PullReport(downloaded=["1", "2"], skipped=[], still_recording=[])
    folder = tmp_path / "pearl.test" / "1"
    assert (folder / "1.mp4").read_bytes() == CONTENT["1"]
    entries = load_index(folder)
    assert [e["id"] for e in entries] == ["1", "2"]
    assert entries[0]["sha256"] == hashlib.sha256(CONTENT["1"]).hexdigest()
    assert entries[0]["path"] == "1.mp4"
    assert (entries[0]["created"], entries[0]["size"], entries[0]["recorder"]) == (
        "2026-12-11T17:32:10",
        10,
        "1",
    )


async def test_second_pull_downloads_nothing_new(tmp_path: Path) -> None:
    device = Device(_listing())
    folder = tmp_path / "1"
    async with _client(device) as client:
        await pull(client, "1", folder)
        device.downloads.clear()
        report = await pull(client, "1", folder)
    assert device.downloads == []
    assert report == PullReport(downloaded=[], skipped=["1", "2"], still_recording=[])
    assert len(load_index(folder)) == 2


async def test_a_file_still_recording_is_reported_not_downloaded(tmp_path: Path) -> None:
    device = Device(_listing(**{"2": {"recording": True}}))
    folder = tmp_path / "1"
    async with _client(device) as client:
        report = await pull(client, "1", folder)
        assert report.still_recording == ["2"] and report.downloaded == ["1"]
        assert device.downloads == ["1"]
        device.listing = _listing()
        report = await pull(client, "1", folder)
    assert report.downloaded == ["2"] and report.skipped == ["1"]


async def test_an_interrupted_pull_leaves_no_partial_file_and_no_index_line(tmp_path: Path) -> None:
    device = Device(_listing(), fail_on="2")
    folder = tmp_path / "1"
    async with _client(device) as client:
        with pytest.raises(httpx.ReadError):
            await pull(client, "1", folder)
        assert sorted(p.name for p in folder.iterdir()) == ["1.mp4", "index.jsonl"]
        assert [e["id"] for e in load_index(folder)] == ["1"]
        device.fail_on = None
        report = await pull(client, "1", folder)
    assert report.downloaded == ["2"] and report.skipped == ["1"]
    assert [e["id"] for e in load_index(folder)] == ["1", "2"]


async def test_index_lines_are_json_objects_one_per_line(tmp_path: Path) -> None:
    async with _client(Device(_listing())) as client:
        await pull(client, "1", tmp_path)
    lines = (tmp_path / "index.jsonl").read_text().splitlines()
    assert len(lines) == 2 and all(isinstance(json.loads(line), dict) for line in lines)


def test_load_index_of_a_missing_folder_is_empty(tmp_path: Path) -> None:
    assert load_index(tmp_path / "nothing") == []


async def test_an_unsafe_file_id_from_the_device_is_refused_before_any_download(tmp_path: Path) -> None:
    listing = _listing()
    listing[0]["id"] = "../../escape"
    device = Device(listing)
    async with _client(device) as client:
        with pytest.raises(ValueError, match="unsafe"):
            await pull(client, "1", tmp_path / "1")
    assert device.downloads == []

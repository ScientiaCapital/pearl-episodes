import hashlib
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from pearl_episodes.config import Settings
from pearl_episodes.episodes.manifest import sha256_of
from pearl_episodes.pearl import client as client_module
from pearl_episodes.pearl.client import (
    PAGE_SIZE,
    FileStillRecording,
    IncompleteDownload,
    PearlApiError,
    PearlClient,
    RecordingFile,
    UnsafeIdError,
)


def _settings() -> Settings:
    return Settings(host="pearl.test", password="x")


def _file(i: int) -> dict[str, object]:
    return {
        "id": str(i),
        "name": f"HDMI-A_Dec11_17-32-{i:02d}",
        "extension": "mp4",
        "recording": False,
        "downloaded": False,
        "created": "2026-12-11T17:32:30",
        "duration": 60,
        "size": 1000 + i,
        "recorder": "1",
        "uploading": False,
    }


async def test_list_recordings_pages_with_from_and_limit() -> None:
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v2.0/recorders/1/archive/files"
        start = int(request.url.params["from"])
        seen.append((request.url.params["from"], request.url.params["limit"]))
        total = PAGE_SIZE + 5
        items = [_file(i) for i in range(start, min(start + PAGE_SIZE, total))]
        return httpx.Response(200, json={"status": "ok", "result": items})

    async with PearlClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        files = await client.list_recordings("1")
    assert len(files) == PAGE_SIZE + 5
    assert seen == [("0", str(PAGE_SIZE)), (str(PAGE_SIZE), str(PAGE_SIZE))]


async def test_device_info_reads_ident_and_firmware() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/system/ident"):
            return httpx.Response(
                200, json={"status": "ok", "result": {"name": "Bench Mini", "location": "Home"}}
            )
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "result": {
                    "version": "4.24.6",
                    "revision": "r1",
                    "product_id": 7,
                    "product_name": "Pearl Mini",
                },
            },
        )

    async with PearlClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        info = await client.device_info()
    assert (
        info.firmware_version == "4.24.6" and info.product_name == "Pearl Mini" and info.name == "Bench Mini"
    )


async def test_bulk_start_sends_ids_filter() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST" and request.url.path == "/api/v2.0/recorders/control/start"
        assert request.url.params["ids"] == "1,2"
        return httpx.Response(200, json={"status": "ok"})

    async with PearlClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        await client.start_all(["1", "2"])


# Issue #2: every Pearl response is `{"status": "ok", "result": ...}`; anything else is an error, never an
# empty result.


def _client(body: object, status_code: int = 200) -> PearlClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=body)

    return PearlClient(_settings(), transport=httpx.MockTransport(handler))


async def test_non_ok_status_in_a_200_body_raises() -> None:
    async with _client({"status": "error", "message": "recorder busy"}) as client:
        with pytest.raises(PearlApiError) as info:
            await client.list_recorders()
    assert info.value.path == "/recorders"
    assert "recorder busy" in str(info.value)


async def test_ok_body_without_result_raises() -> None:
    async with _client({"status": "ok"}) as client:
        with pytest.raises(PearlApiError):
            await client.list_recorders()


@pytest.mark.parametrize("status_code", [401, 404, 500])
async def test_http_errors_raise(status_code: int) -> None:
    async with _client({"status": "error"}, status_code) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.list_recordings("1")


async def test_result_of_the_wrong_type_raises() -> None:
    async with _client({"status": "ok", "result": {"id": "1"}}) as client:
        with pytest.raises(PearlApiError):
            await client.list_recorders()
    async with _client({"status": "ok", "result": [1, 2]}) as client:
        with pytest.raises(PearlApiError):
            await client.device_info()


async def test_device_info_missing_fields_are_none_not_empty() -> None:
    async with _client({"status": "ok", "result": {"version": "4.24.6"}}) as client:
        info = await client.device_info()
    assert info.firmware_version == "4.24.6"
    assert info.name is None and info.location is None and info.product_name is None


async def test_bulk_start_with_non_ok_status_raises() -> None:
    async with _client({"status": "error", "message": "no such recorder"}) as client:
        with pytest.raises(PearlApiError):
            await client.start_all(["9"])


# Issue #3: downloads are atomic and size-verified, and refuse files the device is still writing.


def _recording_file(size: int | None, **flags: bool) -> RecordingFile:
    return RecordingFile.model_validate({**_file(7), "size": size, **flags})


def _streaming_client(chunks: list[bytes], headers: dict[str, str] | None = None) -> PearlClient:
    async def body() -> AsyncIterator[bytes]:
        for chunk in chunks:
            yield chunk

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v2.0/recorders/1/archive/files/7"
        return httpx.Response(200, content=body(), headers=headers)

    return PearlClient(_settings(), transport=httpx.MockTransport(handler))


async def test_download_streams_chunks_to_the_final_path_with_the_right_hash(tmp_path: Path) -> None:
    chunks = [b"abc", b"def", b"ghi"]
    dest = tmp_path / "out" / "7.mp4"
    async with _streaming_client(chunks, {"Content-Length": "9"}) as client:
        await client.download("1", _recording_file(size=9), dest)
    assert dest.read_bytes() == b"abcdefghi"
    assert sha256_of(dest) == hashlib.sha256(b"abcdefghi").hexdigest()
    assert list(tmp_path.rglob("*.part")) == []


async def test_download_that_drops_mid_stream_leaves_no_file(tmp_path: Path) -> None:
    async def body() -> AsyncIterator[bytes]:
        yield b"abc"
        raise httpx.ReadError("connection dropped")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body())

    dest = tmp_path / "7.mp4"
    async with PearlClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.ReadError):
            await client.download("1", _recording_file(size=9), dest)
    assert list(tmp_path.iterdir()) == []


async def test_download_404_leaves_no_file(tmp_path: Path) -> None:
    dest = tmp_path / "7.mp4"
    async with _client({"status": "error"}, 404) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.download("1", _recording_file(size=9), dest)
    assert list(tmp_path.iterdir()) == []


async def test_download_shorter_than_content_length_raises_and_cleans_up(tmp_path: Path) -> None:
    dest = tmp_path / "7.mp4"
    async with _streaming_client([b"abc"], {"Content-Length": "9"}) as client:
        with pytest.raises(IncompleteDownload) as info:
            await client.download("1", _recording_file(size=None), dest)
    assert (info.value.expected, info.value.got) == (9, 3)
    assert list(tmp_path.iterdir()) == []


async def test_download_differing_from_archive_size_raises(tmp_path: Path) -> None:
    dest = tmp_path / "7.mp4"
    async with _streaming_client([b"abc"]) as client:
        with pytest.raises(IncompleteDownload):
            await client.download("1", _recording_file(size=4), dest)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("flag", ["recording", "uploading"])
async def test_download_refuses_a_file_the_device_is_still_writing(tmp_path: Path, flag: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be made")

    async with PearlClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FileStillRecording):
            await client.download("1", _recording_file(size=9, **{flag: True}), tmp_path / "7.mp4")
    assert list(tmp_path.iterdir()) == []


# Issue #4: recorder status (`pearl-family/pearl-rest-api-check-recorder-status-and-download-recordings`).
# Start and stop are asynchronous, so a session must read the state back.


async def test_recorder_status_for_several_recorders_sends_ids_and_parses_nested_status() -> None:
    result = [
        {
            "id": "1",
            "name": "Wide Cam",
            "status": {"state": "started", "duration": 195, "active": "1", "total": "1"},
        },
        {"id": "2", "name": "Side Cam", "status": {"state": "stopped"}},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v2.0/recorders/status"
        assert request.url.params["ids"] == "1,2"
        return httpx.Response(200, json={"status": "ok", "result": result})

    async with PearlClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        statuses = await client.recorder_status(["1", "2"])
    assert [(s.id, s.status.state, s.status.duration) for s in statuses] == [
        ("1", "started", 195),
        ("2", "stopped", None),
    ]


async def test_recorder_status_one_parses_error_state_with_description() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v2.0/recorders/1/status"
        return httpx.Response(
            200, json={"status": "ok", "result": {"state": "error", "description": "Disk full"}}
        )

    async with PearlClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        status = await client.recorder_status_one("1")
    assert (status.state, status.description) == ("error", "Disk full")


async def test_recorder_status_rejects_an_unknown_state() -> None:
    async with _client({"status": "ok", "result": {"state": "paused"}}) as client:
        with pytest.raises(ValidationError):
            await client.recorder_status_one("1")


# Issue #13: gaps found in the 2026-10-14 test review.


async def test_listing_with_exactly_one_full_page_asks_once_more_and_stops() -> None:
    seen: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        start = int(request.url.params["from"])
        seen.append(start)
        items = [_file(i) for i in range(start, PAGE_SIZE)]
        return httpx.Response(200, json={"status": "ok", "result": items})

    async with PearlClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        files = await client.list_recordings("1")
    assert len(files) == PAGE_SIZE and seen == [0, PAGE_SIZE]


async def test_a_device_that_ignores_from_raises_instead_of_paging_forever() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert calls <= 3, "runaway paging: the client never noticed the page repeating"
        return httpx.Response(200, json={"status": "ok", "result": [_file(i) for i in range(PAGE_SIZE)]})

    async with PearlClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(PearlApiError, match="advance"):
            await client.list_recordings("1")


async def test_requests_carry_a_basic_auth_header() -> None:
    headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        headers.append(request.headers["authorization"])
        return httpx.Response(200, json={"status": "ok", "result": []})

    async with PearlClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        await client.list_recorders()
    assert headers == ["Basic YWRtaW46eA=="]  # base64 of "admin:x"


@pytest.mark.parametrize("action", ["start_all", "stop_all"])
async def test_bulk_control_all_recorders_sends_no_ids_filter(action: str) -> None:
    seen: list[tuple[str, bool]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, "ids" in request.url.params))
        return httpx.Response(200, json={"status": "ok"})

    async with PearlClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        await getattr(client, action)(all_recorders=True)
    assert seen == [(f"/api/v2.0/recorders/control/{action.removesuffix('_all')}", False)]


@pytest.mark.parametrize("action", ["start_all", "stop_all"])
@pytest.mark.parametrize(
    "kwargs", [{}, {"ids": []}, {"ids": ["1"], "all_recorders": True}], ids=["neither", "empty", "both"]
)
async def test_bulk_control_must_name_recorders_or_ask_for_all(action: str, kwargs: dict) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request may reach the device")

    async with PearlClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="all_recorders"):
            await getattr(client, action)(**kwargs)


async def test_recorder_status_without_ids_sends_no_ids_filter() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "ids" not in request.url.params
        return httpx.Response(200, json={"status": "ok", "result": []})

    async with PearlClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        assert await client.recorder_status() == []


# Ids from the caller or the device go into URL paths, so they must be plain names.

UNSAFE_IDS = ["../system", "1/../../x", "", ".hidden", "1?x=y", "1#frag", "a b", "%2e%2e"]


def _no_request_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"no request may reach the device: {request.url}")

    return httpx.MockTransport(handler)


@pytest.mark.parametrize("bad", UNSAFE_IDS)
async def test_an_unsafe_recorder_id_never_reaches_a_url(bad: str, tmp_path: Path) -> None:
    async with PearlClient(_settings(), transport=_no_request_transport()) as client:
        with pytest.raises(UnsafeIdError):
            await client.recorder_status_one(bad)
        with pytest.raises(UnsafeIdError):
            await client.list_recordings(bad)
        with pytest.raises(UnsafeIdError):
            await client.download(bad, _recording_file(size=9), tmp_path / "7.mp4")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("bad", UNSAFE_IDS)
async def test_an_unsafe_file_id_never_reaches_a_url(bad: str, tmp_path: Path) -> None:
    file = RecordingFile.model_validate({**_file(7), "id": bad, "size": 9})
    async with PearlClient(_settings(), transport=_no_request_transport()) as client:
        with pytest.raises(UnsafeIdError):
            await client.download("1", file, tmp_path / "7.mp4")
    assert list(tmp_path.iterdir()) == []


def test_unsafe_id_error_is_a_value_error() -> None:
    assert issubclass(UnsafeIdError, ValueError)


# Download size: a device that sends more than it promised, or a nonsense Content-Length, is refused.


async def test_download_stops_reading_once_it_passes_the_listing_size(tmp_path: Path) -> None:
    served: list[int] = []

    async def body() -> AsyncIterator[bytes]:
        for i in range(1000):
            served.append(i)
            yield b"x" * 1024

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body())

    async with PearlClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(IncompleteDownload) as info:
            await client.download("1", _recording_file(size=2048), tmp_path / "7.mp4")
    assert info.value.expected == 2048
    assert len(served) < 10
    assert list(tmp_path.iterdir()) == []


async def test_download_without_any_size_is_capped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_module, "MAX_DOWNLOAD_BYTES", 4096)

    async def body() -> AsyncIterator[bytes]:
        for _ in range(1000):
            yield b"x" * 1024

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body())

    async with PearlClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(IncompleteDownload) as info:
            await client.download("1", _recording_file(size=None), tmp_path / "7.mp4")
    assert info.value.expected == 4096
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("length", ["nine", "-9", "9.0", "+9", "1e3", "0x9"])
async def test_download_with_a_bad_content_length_is_a_device_error(tmp_path: Path, length: str) -> None:
    async with _streaming_client([b"abcdefghi"], {"Content-Length": length}) as client:
        with pytest.raises(PearlApiError, match="Content-Length"):
            await client.download("1", _recording_file(size=9), tmp_path / "7.mp4")
    assert list(tmp_path.iterdir()) == []


async def test_download_whose_content_length_disagrees_with_the_listing_is_refused_unread(
    tmp_path: Path,
) -> None:
    served: list[bytes] = []

    async def body() -> AsyncIterator[bytes]:
        served.append(b"abc")
        yield b"abc"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body(), headers={"Content-Length": "999999"})

    async with PearlClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(IncompleteDownload) as info:
            await client.download("1", _recording_file(size=9), tmp_path / "7.mp4")
    assert (info.value.expected, info.value.got) == (9, 999999)
    assert served == []
    assert list(tmp_path.iterdir()) == []


async def test_the_cap_holds_even_when_the_device_promises_more(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(client_module, "MAX_DOWNLOAD_BYTES", 4096)

    async def body() -> AsyncIterator[bytes]:
        for _ in range(1000):
            yield b"x" * 1024

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body(), headers={"Content-Length": str(1000 * 1024)})

    async with PearlClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(IncompleteDownload) as info:
            await client.download("1", _recording_file(size=1000 * 1024), tmp_path / "7.mp4")
    assert info.value.expected == 4096
    assert list(tmp_path.iterdir()) == []

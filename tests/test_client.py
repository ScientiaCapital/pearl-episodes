import httpx
import pytest

from pearl_episodes.config import Settings
from pearl_episodes.pearl.client import PAGE_SIZE, PearlApiError, PearlClient


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

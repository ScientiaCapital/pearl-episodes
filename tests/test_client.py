import httpx

from pearl_episodes.config import Settings
from pearl_episodes.pearl.client import PAGE_SIZE, PearlClient


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

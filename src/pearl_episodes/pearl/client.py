"""Async client for one Pearl device's REST API.

Verified against Epiphan's published OpenAPI spec (github.com/epiphan-video/pearl_api_swagger_ui,
`api/v2.0/openapi.yml`, "Pearl device REST API" v2.0, checked 2026-10-14): base path `/api/v2.0`, HTTP Basic
auth, every response wrapped as `{"status": "ok", "result": ...}`. Paths below are the spec's.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from pearl_episodes.config import Settings

PAGE_SIZE = 100


class RecordingFile(BaseModel):
    """One archive file (spec schema `ArchiveFile`)."""

    id: str
    name: str
    extension: str | None = None
    recording: bool = False
    downloaded: bool = False
    created: str | None = None
    duration: int | None = None
    size: int | None = None
    recorder: str | None = None
    uploading: bool = False
    event_id: str | None = None


class Recorder(BaseModel):
    """One recorder (spec schema `Recorder`); `multisource` marks a multi-track recorder."""

    id: str
    name: str
    multisource: bool = False


class DeviceInfo(BaseModel):
    """Identity and firmware for the manifest. Serial number is not in the REST spec; take it from Edge.

    A field the device did not report is `None`, never an empty string, so the manifest cannot carry a blank
    firmware version as if it had been read.
    """

    name: str | None = None
    location: str | None = None
    firmware_version: str | None = None
    firmware_revision: str | None = None
    product_name: str | None = None


class PearlApiError(Exception):
    """The device answered without `{"status": "ok", "result": ...}`, or the result had the wrong shape."""

    def __init__(self, path: str, status: object, excerpt: str) -> None:
        self.path = path
        self.status = status
        self.excerpt = excerpt
        super().__init__(f"{path}: status={status!r}: {excerpt}")


def _check_envelope(path: str, response: httpx.Response) -> dict[str, Any]:
    """Return the parsed body if it is a dict with `status == "ok"`; raise `PearlApiError` otherwise."""
    excerpt = response.text[:200]
    try:
        body = response.json()
    except ValueError as exc:
        raise PearlApiError(path, None, excerpt) from exc
    if not isinstance(body, dict) or body.get("status") != "ok":
        status = body.get("status") if isinstance(body, dict) else None
        raise PearlApiError(path, status, excerpt)
    return body


class PearlClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.base_url,
            auth=(settings.username, settings.password.get_secret_value()),
            verify=settings.verify_tls,
            timeout=30.0,
            transport=transport,
        )

    async def __aenter__(self) -> PearlClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._client.aclose()

    async def _get_result[T: (list, dict)](
        self, path: str, expect: type[T], params: dict[str, Any] | None = None
    ) -> T:
        """GET `path`; HTTP errors raise `httpx.HTTPStatusError`, a bad envelope or a `result` that is not an
        `expect` raises `PearlApiError`."""
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        body = _check_envelope(path, response)
        if "result" not in body or not isinstance(body["result"], expect):
            excerpt = f"expected a {expect.__name__} result: {response.text[:200]}"
            raise PearlApiError(path, body.get("status"), excerpt)
        return body["result"]

    async def _post(self, path: str, params: dict[str, str] | None = None) -> None:
        """POST a control call. The spec returns the envelope with no `result`."""
        response = await self._client.post(path, params=params)
        response.raise_for_status()
        _check_envelope(path, response)

    async def list_recorders(self) -> list[Recorder]:
        return [Recorder.model_validate(r) for r in await self._get_result("/recorders", list)]

    async def device_info(self) -> DeviceInfo:
        ident = await self._get_result("/system/ident", dict)
        fw = await self._get_result("/system/firmware", dict)
        return DeviceInfo(
            name=ident.get("name"),
            location=ident.get("location"),
            firmware_version=fw.get("version"),
            firmware_revision=fw.get("revision"),
            product_name=fw.get("product_name"),
        )

    async def list_recordings(self, recorder_id: str) -> list[RecordingFile]:
        """All archive files for one recorder, paged with the spec's `from` and `limit` parameters."""
        files: list[RecordingFile] = []
        while True:
            page = await self._get_result(
                f"/recorders/{recorder_id}/archive/files", list, {"from": len(files), "limit": PAGE_SIZE}
            )
            batch = [RecordingFile.model_validate(item) for item in page]
            files.extend(batch)
            if len(batch) < PAGE_SIZE:
                return files

    async def download(self, recorder_id: str, file_id: str, dest: Path) -> Path:
        """Stream one recording to disk (`application/octet-stream`). Missing recorder or file is a 404."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        async with self._client.stream("GET", f"/recorders/{recorder_id}/archive/files/{file_id}") as r:
            r.raise_for_status()
            with dest.open("wb") as fh:
                async for chunk in r.aiter_bytes():
                    fh.write(chunk)
        return dest

    async def start_all(self, ids: list[str] | None = None) -> None:
        """Bulk start. Asynchronous: returns when the command is accepted, not when recorders are running."""
        await self._post("/recorders/control/start", params=_ids(ids))

    async def stop_all(self, ids: list[str] | None = None) -> None:
        await self._post("/recorders/control/stop", params=_ids(ids))


def _ids(ids: list[str] | None) -> dict[str, str] | None:
    return {"ids": ",".join(ids)} if ids else None

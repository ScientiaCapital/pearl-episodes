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
    """Identity and firmware for the manifest. Serial number is not in the REST spec; take it from Edge."""

    name: str = ""
    location: str = ""
    firmware_version: str = ""
    firmware_revision: str = ""
    product_name: str = ""


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

    async def _get_result(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        return response.json().get("result")

    async def list_recorders(self) -> list[Recorder]:
        return [Recorder.model_validate(r) for r in await self._get_result("/recorders") or []]

    async def device_info(self) -> DeviceInfo:
        ident = await self._get_result("/system/ident") or {}
        fw = await self._get_result("/system/firmware") or {}
        return DeviceInfo(
            name=ident.get("name", ""),
            location=ident.get("location", ""),
            firmware_version=fw.get("version", ""),
            firmware_revision=fw.get("revision", ""),
            product_name=fw.get("product_name", ""),
        )

    async def list_recordings(self, recorder_id: str) -> list[RecordingFile]:
        """All archive files for one recorder, paged with the spec's `from` and `limit` parameters."""
        files: list[RecordingFile] = []
        while True:
            page = await self._get_result(
                f"/recorders/{recorder_id}/archive/files", {"from": len(files), "limit": PAGE_SIZE}
            )
            batch = [RecordingFile.model_validate(item) for item in page or []]
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
        response = await self._client.post("/recorders/control/start", params=_ids(ids))
        response.raise_for_status()

    async def stop_all(self, ids: list[str] | None = None) -> None:
        response = await self._client.post("/recorders/control/stop", params=_ids(ids))
        response.raise_for_status()


def _ids(ids: list[str] | None) -> dict[str, str] | None:
    return {"ids": ",".join(ids)} if ids else None

"""Async client for one Pearl device's REST API.

Endpoint paths follow the product documentation (kb.epiphan.com, pearl-family/pearl-rest-api-*).
The URL prefix and auth scheme are configuration until confirmed against a real device.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
from pydantic import BaseModel

from pearl_episodes.config import Settings


class RecordingFile(BaseModel):
    """One recording as the Pearl archive listing describes it."""

    id: str
    name: str
    extension: str | None = None
    recording: bool = False
    downloaded: bool = False
    created: str | None = None
    duration: float | None = None
    size: int | None = None
    recorder: str | None = None
    uploading: bool = False
    event_id: str | None = None


class PearlClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.base_url,
            auth=(settings.username, settings.password),
            verify=settings.verify_tls,
            timeout=30.0,
        )

    async def __aenter__(self) -> PearlClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._client.aclose()

    async def list_recordings(self, recorder_id: str) -> list[RecordingFile]:
        """List archived files for one recorder (channel or multi-track recorder)."""
        response = await self._client.get(f"/recorders/{recorder_id}/archive/files")
        response.raise_for_status()
        payload = response.json()
        items = payload.get("result", payload) if isinstance(payload, dict) else payload
        return [RecordingFile.model_validate(item) for item in items]

    async def download(self, recorder_id: str, file_id: str, dest: Path) -> Path:
        """Stream one recording to disk. Returns the written path."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        async with self._client.stream("GET", f"/recorders/{recorder_id}/archive/files/{file_id}") as r:
            r.raise_for_status()
            with dest.open("wb") as fh:
                async for chunk in r.aiter_bytes():
                    fh.write(chunk)
        return dest

    async def start_all(self, ids: list[str] | None = None) -> None:
        """Bulk start. The device accepts the command and returns before recorders start."""
        params = {"ids": ",".join(ids)} if ids else None
        response = await self._client.post("/recorders/control/start", params=params)
        response.raise_for_status()

    async def stop_all(self, ids: list[str] | None = None) -> None:
        params = {"ids": ",".join(ids)} if ids else None
        response = await self._client.post("/recorders/control/stop", params=params)
        response.raise_for_status()

    async def iter_new_recordings(self, recorder_id: str, seen: set[str]) -> AsyncIterator[RecordingFile]:
        for item in await self.list_recordings(recorder_id):
            if item.id not in seen and not item.recording:
                yield item

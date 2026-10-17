"""Read-only preflight for an operator session: is each channel fit to start a take?

Pure functions over what the Epiphan Edge read tools return (`get_devices_in_my_team`,
`get_storage_status_for_devices`, `get_channel_settings`). Nothing here calls a tool, the network or a
device; a Claude session gathers the JSON (`.claude/commands/preflight.md`) and
`pearl-episodes preflight` evaluates it.

Each check is `pass`, `fail` or `unverified`. `unverified` is for what the documentation does not settle,
and it does not fail the run. Device and channel warnings are copied verbatim. Nothing here says anything
about timing or alignment between cameras or devices.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Our own policy, not a product fact: a full drive overwrites the oldest files, so refuse well before that.
DEFAULT_MIN_FREE_BYTES = 10 * 1000**3
# kb: pearl-family/configure-recording-settings-file-size-and-type: a channel controlled by Epiphan Edge must
# record MP4 with a maximum file size of 500 MB.
MAX_EDGE_FILE_SIZE_MB = 500
STORAGE_WARNING_IDS = frozenset({"disk_space_error", "no_storage_detected"})
NO_SIGNAL_WARNING_ID = "channel_no_signal"

Status = Literal["pass", "fail", "unverified"]


class _Edge(BaseModel):
    """What the Edge tools return. The payloads are wide, so unknown fields are ignored."""

    model_config = ConfigDict(frozen=True, extra="ignore", populate_by_name=True)


class EdgeWarning(_Edge):
    id: str
    message: str = ""


class EdgeRecordingStatus(_Edge):
    state: str
    description: str = ""


class EdgeChannel(_Edge):
    channel_id: str
    name: str = ""
    warnings: list[EdgeWarning] = Field(default_factory=list, alias="Warnings")
    recording_status: EdgeRecordingStatus | None = None


class EdgeDevice(_Edge):
    id: str = Field(alias="Id")
    name: str = Field(default="", alias="Name")
    status: str = Field(alias="Status")
    channels: list[EdgeChannel] = Field(default_factory=list, alias="Channels")
    warnings: list[EdgeWarning] = Field(default_factory=list, alias="Warnings")


class EdgeStorage(_Edge):
    device_id: str
    state: str
    total_bytes: int | None = None
    free_bytes: int | None = None


class EdgeSetting(_Edge):
    id: str
    value: str


class PreflightInput(_Edge):
    """`devices` and `storage` are the lists from the two tools. `channel_settings` maps
    `<device>-<channel>` to the `settings` list of `get_channel_settings`."""

    devices: list[EdgeDevice]
    storage: list[EdgeStorage] = Field(default_factory=list)
    channel_settings: dict[str, list[EdgeSetting]] = Field(default_factory=dict)


class _Out(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Check(_Out):
    name: str
    status: Status
    detail: str = ""


class ChannelReport(_Out):
    address: str = Field(description="`<device_id>-<channel_id>`, the Edge batch address")
    device_name: str = ""
    channel_name: str = ""
    checks: list[Check]
    warnings: list[str] = Field(default_factory=list, description="Device and channel warnings, verbatim")

    @property
    def ok(self) -> bool:
        return all(c.status != "fail" for c in self.checks)


class PreflightReport(_Out):
    channels: list[ChannelReport]

    @property
    def ok(self) -> bool:
        return bool(self.channels) and all(c.ok for c in self.channels)


_SIZE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(KB|MB|GB|TB)\s*$", re.IGNORECASE)
_MB_PER_UNIT = {"kb": 0.001, "mb": 1.0, "gb": 1000.0, "tb": 1_000_000.0}


def size_limit_mb(value: str) -> float | None:
    """`'500 MB'` -> 500.0, read as written with decimal units. `None` for `'unlimited'` or anything else."""
    match = _SIZE.match(value)
    return None if match is None else float(match.group(1)) * _MB_PER_UNIT[match.group(2).lower()]


def _warning_texts(device: EdgeDevice, channel: EdgeChannel) -> list[str]:
    return [w.message or w.id for w in (*device.warnings, *channel.warnings)]


def _check_online(device: EdgeDevice) -> Check:
    return Check(
        name="online",
        status="pass" if device.status == "online" else "fail",
        detail=f"Edge reports {device.status!r}",
    )


def _check_storage(device: EdgeDevice, storage: EdgeStorage | None, min_free_bytes: int) -> Check:
    flagged = [w.id for w in device.warnings if w.id in STORAGE_WARNING_IDS]
    if flagged:
        return Check(name="storage", status="fail", detail=f"device warning {', '.join(flagged)}")
    if storage is None:
        return Check(name="storage", status="fail", detail="no storage status returned for this device")
    if storage.state != "ready":
        return Check(name="storage", status="fail", detail=f"storage state is {storage.state!r}")
    if storage.free_bytes is None:
        return Check(name="storage", status="fail", detail="storage is ready but free space is not reported")
    if storage.free_bytes < min_free_bytes:
        return Check(
            name="storage",
            status="fail",
            detail=f"{storage.free_bytes} bytes free, below the floor of {min_free_bytes}",
        )
    return Check(name="storage", status="pass", detail=f"{storage.free_bytes} bytes free")


def _check_recorder(channel: EdgeChannel) -> Check:
    if channel.recording_status is None:
        return Check(name="recorder", status="fail", detail="no recording status reported")
    state = channel.recording_status.state
    if state == "stopped":
        return Check(name="recorder", status="pass", detail="stopped, ready to start")
    detail = f"state is {state!r}"
    if channel.recording_status.description:
        detail += f": {channel.recording_status.description}"
    return Check(name="recorder", status="fail", detail=detail)


def _check_signal(channel: EdgeChannel) -> Check:
    if any(w.id == NO_SIGNAL_WARNING_ID for w in channel.warnings):
        return Check(name="signal", status="fail", detail="channel reports no signal")
    return Check(name="signal", status="pass")


def _check_file_format(settings: dict[str, str] | None) -> Check:
    name = "file-format"
    if settings is None or "recorder.file_format" not in settings:
        return Check(name=name, status="unverified", detail="channel settings not provided")
    value = settings["recorder.file_format"]
    if value == "MP4":
        return Check(name=name, status="pass", detail=value)
    if value.upper().startswith("MP4"):
        # The kb says "MP4"; it does not say whether a variant like this is accepted under Edge control.
        return Check(name=name, status="unverified", detail=f"device reports {value!r}; the kb says MP4")
    return Check(name=name, status="fail", detail=f"device reports {value!r}; the kb says MP4")


def _check_size_limit(settings: dict[str, str] | None) -> Check:
    name = "file-size-limit"
    if settings is None or "recorder.size_limit" not in settings:
        return Check(name=name, status="unverified", detail="channel settings not provided")
    value = settings["recorder.size_limit"]
    limit = size_limit_mb(value)
    if limit is None or limit > MAX_EDGE_FILE_SIZE_MB:
        return Check(name=name, status="fail", detail=f"device reports {value!r}; the kb says 500 MB maximum")
    return Check(name=name, status="pass", detail=value)


def _channel_report(
    address: str, data: PreflightInput, storage_by_device: dict[str, EdgeStorage], min_free_bytes: int
) -> ChannelReport:
    device_id, _, channel_id = address.rpartition("-")
    device = next((d for d in data.devices if d.id == device_id), None)
    channel = (
        None if device is None else next((c for c in device.channels if c.channel_id == channel_id), None)
    )
    if device is None or channel is None:
        return ChannelReport(
            address=address,
            checks=[Check(name="found", status="fail", detail="no such device and channel in the input")],
        )
    raw = data.channel_settings.get(address)
    settings = None if raw is None else {s.id: s.value for s in raw}
    return ChannelReport(
        address=address,
        device_name=device.name,
        channel_name=channel.name,
        checks=[
            _check_online(device),
            _check_storage(device, storage_by_device.get(device.id), min_free_bytes),
            _check_recorder(channel),
            _check_signal(channel),
            _check_file_format(settings),
            _check_size_limit(settings),
        ],
        warnings=_warning_texts(device, channel),
    )


def evaluate_preflight(
    data: PreflightInput, channels: Sequence[str], min_free_bytes: int = DEFAULT_MIN_FREE_BYTES
) -> PreflightReport:
    """Check each `<device_id>-<channel_id>` address. A channel the input does not contain fails `found`."""
    storage_by_device = {s.device_id: s for s in data.storage}
    return PreflightReport(
        channels=[_channel_report(a, data, storage_by_device, min_free_bytes) for a in channels]
    )


def format_report(report: PreflightReport) -> str:
    """One block per channel, one line per check, then the verbatim warnings."""
    lines: list[str] = []
    for channel in report.channels:
        label = " / ".join(p for p in (channel.device_name, channel.channel_name) if p)
        lines.append(f"{channel.address}  {label}  {'OK' if channel.ok else 'NOT READY'}")
        lines.extend(
            f"  {c.status.upper():<10} {c.name}" + (f": {c.detail}" if c.detail else "")
            for c in channel.checks
        )
        lines.extend(f"  warning: {w}" for w in channel.warnings)
    lines.append("preflight: " + ("ready" if report.ok else "not ready"))
    return "\n".join(lines)

import json
from pathlib import Path

import pytest

from pearl_episodes.cli import main
from pearl_episodes.operate.preflight import (
    DEFAULT_MIN_FREE_BYTES,
    PreflightInput,
    PreflightReport,
    evaluate_preflight,
    format_report,
    size_limit_mb,
)

ADDRESS = "TESTDEV0001-1"
GOOD_SETTINGS = [
    {"id": "recorder.file_format", "value": "MP4", "description": "File Type"},
    {"id": "recorder.size_limit", "value": "500 MB", "description": "Size Limit"},
]


def make_input(
    *,
    status: str = "online",
    device_warnings: list[dict] | None = None,
    channel_warnings: list[dict] | None = None,
    recorder_state: str = "stopped",
    storage: dict | None = None,
    settings: list[dict] | None = None,
) -> dict:
    """Edge-shaped input for one device, "Room 204 Pearl Mini", with one channel. Placeholders only."""
    channel: dict = {
        "channel_id": "1",
        "name": "Camera A",
        "recording_status": {"state": recorder_state, "description": "recording is not started"},
    }
    if channel_warnings:
        channel["Warnings"] = channel_warnings
    device: dict = {
        "Id": "TESTDEV0001",
        "Name": "Room 204 Pearl Mini",
        "Status": status,
        "Channels": [channel],
    }
    if device_warnings:
        device["Warnings"] = device_warnings
    return {
        "devices": [device],
        "storage": [
            storage
            or {
                "device_id": "TESTDEV0001",
                "state": "ready",
                "total_bytes": 500 * 1000**3,
                "free_bytes": 200 * 1000**3,
            }
        ],
        "channel_settings": {ADDRESS: GOOD_SETTINGS if settings is None else settings},
    }


def evaluate(data: dict | None = None, channels: tuple[str, ...] = (ADDRESS,)) -> PreflightReport:
    return evaluate_preflight(PreflightInput.model_validate(make_input() if data is None else data), channels)


def run(**kwargs: object) -> dict[str, str]:
    report = evaluate(make_input(**kwargs))
    return {c.name: c.status for c in report.channels[0].checks}


def test_all_checks_pass() -> None:
    report = evaluate()
    assert report.ok
    assert {c.status for c in report.channels[0].checks} == {"pass"}
    assert "preflight: ready" in format_report(report)


def test_offline_device_fails() -> None:
    assert run(status="offline")["online"] == "fail"


def test_recorder_must_be_stopped() -> None:
    assert run(recorder_state="error")["recorder"] == "fail"
    assert run(recorder_state="started")["recorder"] == "fail"


def test_no_signal_fails() -> None:
    warning = [{"id": "channel_no_signal", "message": "Channel 'Camera A' has no signal"}]
    assert run(channel_warnings=warning)["signal"] == "fail"


@pytest.mark.parametrize("warning_id", ["disk_space_error", "no_storage_detected"])
def test_storage_device_warning_fails(warning_id: str) -> None:
    assert run(device_warnings=[{"id": warning_id, "message": "x"}])["storage"] == "fail"


def test_free_space_below_floor_fails() -> None:
    low = {
        "device_id": "TESTDEV0001",
        "state": "ready",
        "total_bytes": 10**12,
        "free_bytes": DEFAULT_MIN_FREE_BYTES - 1,
    }
    assert run(storage=low)["storage"] == "fail"


def test_storage_not_ready_fails() -> None:
    assert run(storage={"device_id": "TESTDEV0001", "state": "nodev"})["storage"] == "fail"


def test_missing_storage_entry_fails() -> None:
    data = make_input()
    data["storage"] = []
    report = evaluate(data)
    assert report.channels[0].checks[1].status == "fail"


def test_unknown_channel_fails_found() -> None:
    report = evaluate(channels=["TESTDEV0001-9", "NOPE-1"])
    assert not report.ok
    assert [c.checks[0].name for c in report.channels] == ["found", "found"]


def test_no_channels_requested_is_not_ready() -> None:
    assert not evaluate(channels=[]).ok


def test_file_format_and_size_limit() -> None:
    def settings(fmt: str, size: str) -> list[dict]:
        return [{"id": "recorder.file_format", "value": fmt}, {"id": "recorder.size_limit", "value": size}]

    assert run(settings=settings("MKV", "500 MB"))["file-format"] == "fail"
    assert run(settings=settings("MP4", "64 GB"))["file-size-limit"] == "fail"
    assert run(settings=settings("MP4", "unlimited"))["file-size-limit"] == "fail"
    assert run(settings=settings("MP4", "0.5 GB"))["file-size-limit"] == "pass"


def test_mp4_variant_is_unverified_not_failed() -> None:
    settings = [{"id": "recorder.file_format", "value": "MP4 Fragmented"}] + GOOD_SETTINGS[1:]
    report = evaluate(make_input(settings=settings))
    assert {c.name: c.status for c in report.channels[0].checks}["file-format"] == "unverified"
    assert report.ok


def test_missing_settings_are_unverified() -> None:
    result = run(settings=[])
    assert result["file-format"] == "unverified"
    assert result["file-size-limit"] == "unverified"


def test_warnings_are_copied_verbatim() -> None:
    data = make_input(
        device_warnings=[{"id": "source_no_signal", "message": "Source 'HDMI' has no signal"}],
        channel_warnings=[{"id": "channel_no_signal", "message": "Channel 'Camera A' has no signal"}],
    )
    report = evaluate(data)
    assert report.channels[0].warnings == ["Source 'HDMI' has no signal", "Channel 'Camera A' has no signal"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("500 MB", 500.0),
        ("1 GB", 1000.0),
        ("64 GB", 64000.0),
        ("unlimited", None),
        ("", None),
        ("30 min", None),
    ],
)
def test_size_limit_mb(text: str, expected: float | None) -> None:
    assert size_limit_mb(text) == expected


def test_cli_exit_codes_and_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    good = tmp_path / "good.json"
    good.write_text(json.dumps(make_input()))
    assert main(["preflight", str(good), "--channel", ADDRESS]) == 0
    assert "preflight: ready" in capsys.readouterr().out

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(make_input(status="offline")))
    assert main(["preflight", str(bad), "--channel", ADDRESS]) == 1
    assert "NOT READY" in capsys.readouterr().out


def test_cli_min_free_bytes_flag(tmp_path: Path) -> None:
    path = tmp_path / "in.json"
    path.write_text(json.dumps(make_input()))
    assert main(["preflight", str(path), "--channel", ADDRESS, "--min-free-bytes", str(300 * 1000**3)]) == 1


def test_cli_bad_input_prints_one_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["preflight", str(tmp_path / "missing.json"), "--channel", ADDRESS]) == 1
    assert capsys.readouterr().err.startswith("preflight: ")
    broken = tmp_path / "broken.json"
    broken.write_text("{}")
    assert main(["preflight", str(broken), "--channel", ADDRESS]) == 1
    assert capsys.readouterr().err.startswith("preflight: ")

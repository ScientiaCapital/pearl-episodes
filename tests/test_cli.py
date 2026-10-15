"""CLI behaviour (issue #4): one stderr line and exit 1 on every expected failure; `doctor` is honest."""

import importlib.util
from pathlib import Path

import httpx
import pytest

from pearl_episodes.cli import main

PASSWORD = "not-a-real-password"


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEARL_HOST", "pearl.test")
    monkeypatch.setenv("PEARL_PASSWORD", PASSWORD)


def _transport(body: object, status_code: int = 200) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(status_code, json=body))


def _stderr_lines(capsys: pytest.CaptureFixture[str]) -> list[str]:
    return capsys.readouterr().err.splitlines()


def test_recorders_lists_id_name_and_multisource(
    configured: None, capsys: pytest.CaptureFixture[str]
) -> None:
    recorders = [
        {"id": "1", "name": "Wide Cam", "multisource": False},
        {"id": "2", "name": "Both", "multisource": True},
    ]
    code = main(["recorders"], transport=_transport({"status": "ok", "result": recorders}))
    assert code == 0
    assert capsys.readouterr().out.splitlines() == ["1\tWide Cam\tFalse", "2\tBoth\tTrue"]


def test_missing_settings_is_one_stderr_line_and_exit_1(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["recorders"]) == 1
    lines = _stderr_lines(capsys)
    assert len(lines) == 1 and "PEARL_HOST" in lines[0]


def test_connection_failure_is_one_stderr_line_and_exit_1(
    configured: None, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    assert main(["list", "1"], transport=httpx.MockTransport(refuse)) == 1
    lines = _stderr_lines(capsys)
    assert len(lines) == 1 and "connection refused" in lines[0]


def test_http_error_is_one_stderr_line_and_exit_1(
    configured: None, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["list", "1"], transport=_transport({"status": "error"}, 500)) == 1
    lines = _stderr_lines(capsys)
    assert len(lines) == 1 and "500" in lines[0]


def test_bad_envelope_is_one_stderr_line_and_exit_1(
    configured: None, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["recorders"], transport=_transport({"status": "error", "message": "busy"})) == 1
    lines = _stderr_lines(capsys)
    assert len(lines) == 1 and "busy" in lines[0]


def test_doctor_exit_0_prints_host_and_never_the_password(
    configured: None, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["doctor"]) == 0
    out = capsys.readouterr()
    assert "pearl.test" in out.out
    assert PASSWORD not in out.out + out.err


def test_doctor_exit_1_when_settings_are_missing(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["doctor"]) == 1
    assert ".env" in capsys.readouterr().out


def test_doctor_exit_1_when_a_required_module_is_missing(
    configured: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None if name == "httpx" else real(name))
    assert main(["doctor"]) == 1
    assert "httpx" in capsys.readouterr().out


def test_pull_downloads_into_host_and_recorder_folders_and_exits_0(
    configured: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setenv("PEARL_EPISODES_RECORDINGS_DIR", str(tmp_path / "rec"))
    item = {
        "id": "1",
        "name": "Cam",
        "extension": "mp4",
        "recording": False,
        "downloaded": False,
        "created": "2026-12-11T17:32:10",
        "duration": 60,
        "size": 4,
        "recorder": "1",
        "uploading": False,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/archive/files"):
            return httpx.Response(
                200, json={"status": "ok", "result": [item][int(request.url.params["from"]) :]}
            )
        return httpx.Response(200, content=b"data", headers={"Content-Length": "4"})

    assert main(["pull", "1"], transport=httpx.MockTransport(handler)) == 0
    assert (tmp_path / "rec" / "pearl.test" / "1" / "1.mp4").read_bytes() == b"data"
    assert "downloaded 1" in capsys.readouterr().out
    assert main(["pull", "1"], transport=httpx.MockTransport(handler)) == 0
    assert "downloaded 0" in capsys.readouterr().out

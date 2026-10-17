import json
from pathlib import Path
from typing import Any

import anyio
import pytest

from pearl_episodes.cli import main
from pearl_episodes.operate.preflight import PreflightInput, evaluate_preflight
from pearl_episodes.operate.session_log import LogEntry, SessionLog, preflight_entry
from tests.test_preflight import ADDRESS, make_input

# Built from pieces so the repo's secrets hook does not mistake the fixture for a real credential.
CREDENTIALED = "rtmp://" + "user" + ":" + "pw" + "@host.test/app"


def write_input(tmp_path: Path) -> Path:
    path = tmp_path / "in.json"
    path.write_text(json.dumps(make_input()))
    return path


def entry(tool: str = "get_storage_status_for_devices", **fields: Any) -> LogEntry:
    return LogEntry.now(tool, "storage ready", **fields)


async def test_append_writes_one_line_per_entry_in_order(tmp_path: Path) -> None:
    log = SessionLog(tmp_path / "sessions", "s1")
    first, second = entry("a"), entry("b", verdict="keep", note="clean pick")
    await log.append(first)
    await log.append(second)
    lines = log.path.read_text().splitlines()
    assert len(lines) == 2
    assert [json.loads(line)["tool"] for line in lines] == ["a", "b"]
    assert await log.read() == [first, second]


async def test_append_never_rewrites_earlier_lines(tmp_path: Path) -> None:
    log = SessionLog(tmp_path, "s1")
    await log.append(entry("a"))
    before = log.path.read_text()
    await log.append(entry("b"))
    assert log.path.read_text().startswith(before)


async def test_concurrent_appends_each_land_as_a_whole_line(tmp_path: Path) -> None:
    log = SessionLog(tmp_path, "s1")
    async with anyio.create_task_group() as tg:
        for i in range(20):
            tg.start_soon(log.append, entry(f"t{i}"))
    assert sorted(e.tool for e in await log.read()) == sorted(f"t{i}" for i in range(20))


async def test_entries_are_stamped_with_the_machine_clock() -> None:
    assert entry().machine_ts.endswith("+00:00")


@pytest.mark.parametrize("session_id", ["", "../x", "a/b", ".hidden", "-lead", "x" * 65, "a b"])
def test_session_id_must_be_a_safe_file_name(tmp_path: Path, session_id: str) -> None:
    with pytest.raises(ValueError, match="session id"):
        SessionLog(tmp_path, session_id)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("result_summary", CREDENTIALED),
        ("note", CREDENTIALED),
        ("warnings", [CREDENTIALED]),
        ("args", {"url": CREDENTIALED}),
    ],
)
def test_credentialed_url_is_refused(field: str, value: Any) -> None:
    fields = {"result_summary": "ok", field: value}
    with pytest.raises(ValueError, match="credentialed URL"):
        LogEntry.now("tool", **fields)


def test_url_without_credentials_is_allowed() -> None:
    assert entry(note="rtmp://host.test/app").note == "rtmp://host.test/app"


def test_unknown_fields_and_bad_verdicts_are_refused() -> None:
    with pytest.raises(ValueError):
        entry(surprise=1)
    with pytest.raises(ValueError):
        entry(verdict="maybe")


async def test_preflight_entry_summarizes_a_failed_run() -> None:
    warning = [{"id": "disk_space_error", "message": "There is not enough free storage space"}]
    report = evaluate_preflight(PreflightInput.model_validate(make_input(device_warnings=warning)), [ADDRESS])
    e = preflight_entry(report, [ADDRESS])
    assert e.tool == "preflight" and e.args == {"channels": ADDRESS}
    assert e.result_summary == "not ready: 1 of 1 channels (storage)"
    assert e.warnings == ["There is not enough free storage space"]


def test_preflight_entry_for_a_ready_run() -> None:
    report = evaluate_preflight(PreflightInput.model_validate(make_input()), [ADDRESS])
    assert preflight_entry(report, [ADDRESS]).result_summary == "ready"


def test_cli_preflight_appends_to_the_session_log(tmp_path: Path) -> None:
    path = write_input(tmp_path)
    sessions = tmp_path / "sessions"
    argv = [
        "preflight",
        str(path),
        "--channel",
        ADDRESS,
        "--session",
        "bench-1",
        "--sessions-dir",
        str(sessions),
    ]
    assert main(argv) == 0
    assert main(argv) == 0
    lines = (sessions / "bench-1.jsonl").read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["result_summary"] == "ready"


def test_cli_preflight_without_session_writes_nothing(tmp_path: Path) -> None:
    path = write_input(tmp_path)
    assert main(["preflight", str(path), "--channel", ADDRESS, "--sessions-dir", str(tmp_path / "s")]) == 0
    assert not (tmp_path / "s").exists()


def test_cli_preflight_bad_session_id_prints_one_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_input(tmp_path)
    assert main(["preflight", str(path), "--channel", ADDRESS, "--session", "../x"]) == 1
    assert capsys.readouterr().err.startswith("preflight: session log: ")

"""pearl-episodes: doctor | recorders | list | pull | package | export

Every expected failure (settings missing, device unreachable, HTTP error, bad envelope) prints one line to
stderr and exits 1. Anything else is a bug and raises.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx
from pydantic import ValidationError

from pearl_episodes import __version__
from pearl_episodes.config import Settings
from pearl_episodes.episodes.packager import CameraInput, TakeLabels, package_take
from pearl_episodes.episodes.pull import pull
from pearl_episodes.export.lerobot_v3 import ExportError, export_lerobot_v3
from pearl_episodes.media.ffmpeg import RemuxError
from pearl_episodes.pearl.client import PearlApiError, PearlClient

REQUIRED_MODULES = ("httpx", "pydantic", "pydantic_settings")
OPTIONAL_MODULES = ("lerobot", "tensorflow", "tensorflow_datasets")

type Transport = httpx.AsyncBaseTransport | None


def _missing_settings(exc: ValidationError) -> str:
    """`PEARL_HOST, PEARL_...` for every field Settings could not fill."""
    return ", ".join(f"PEARL_{str(e['loc'][0]).upper()}" for e in exc.errors())


def _doctor() -> int:
    import importlib.util

    print(f"pearl-episodes {__version__}")
    ok = True
    for mod in REQUIRED_MODULES + OPTIONAL_MODULES:
        present = importlib.util.find_spec(mod) is not None
        ok &= present or mod in OPTIONAL_MODULES
        label = "ok" if present else ("missing" if mod in REQUIRED_MODULES else "missing (optional)")
        print(f"  {mod:22} {label}")
    try:
        s = Settings()
        print(f"  pearl host            {s.host} ({s.base_url})")
    except ValidationError as exc:
        print(f"  pearl settings        not configured ({_missing_settings(exc)}); copy .env.example to .env")
        ok = False
    return 0 if ok else 1


async def _recorders(client: PearlClient, settings: Settings) -> None:
    for r in await client.list_recorders():
        print(f"{r.id}\t{r.name}\t{r.multisource}")


async def _list(client: PearlClient, settings: Settings, recorder_id: str) -> None:
    for item in await client.list_recordings(recorder_id):
        print(f"{item.id}\t{item.created}\t{item.duration}\t{item.size}\t{item.name}")


async def _pull(client: PearlClient, settings: Settings, recorder_id: str) -> None:
    folder = settings.episodes_recordings_dir / settings.host / recorder_id
    report = await pull(client, recorder_id, folder)
    print(
        f"downloaded {len(report.downloaded)}, already pulled {len(report.skipped)}, "
        f"still recording {len(report.still_recording)}"
    )


def _run(action: Callable[[PearlClient, Settings], Awaitable[None]], transport: Transport) -> int:
    """Open a client from Settings, run `action`, map the expected failures to one stderr line and exit 1."""

    async def go() -> None:
        settings = Settings()
        async with PearlClient(settings, transport=transport) as client:
            await action(client, settings)

    try:
        asyncio.run(go())
    except ValidationError as exc:
        print(f"settings: {_missing_settings(exc)} not set; copy .env.example to .env", file=sys.stderr)
        return 1
    except httpx.HTTPStatusError as exc:
        print(f"{exc.request.url.path}: HTTP {exc.response.status_code}", file=sys.stderr)
        return 1
    except httpx.TransportError as exc:
        print(f"{exc.request.url.host}: {exc}", file=sys.stderr)
        return 1
    except PearlApiError as exc:
        print(f"device error: {exc}", file=sys.stderr)
        return 1
    return 0


def _package(args: argparse.Namespace) -> int:
    """Package pulled files as an episode. Needs settings (folders) and ffmpeg, not the device."""
    try:
        settings = Settings()
    except ValidationError as exc:
        print(f"settings: {_missing_settings(exc)} not set; copy .env.example to .env", file=sys.stderr)
        return 1
    cameras = [
        CameraInput(
            channel_id, channel_name, recorder_id,
            settings.episodes_recordings_dir / settings.host / recorder_id, file_ids.split(","),
        )
        for channel_id, channel_name, recorder_id, file_ids in args.camera
    ]  # fmt: skip
    labels = TakeLabels(
        device_serial=args.serial, device_model=args.model, firmware=args.firmware, task_label=args.task,
        operator=args.operator, scene=args.scene, clock_source=args.clock_source, notes=args.notes,
        session_id=args.session,
    )  # fmt: skip
    try:
        episodes = asyncio.run(package_take(cameras, labels, settings.episodes_output_dir, args.episode_id))
    except (ValueError, FileExistsError, FileNotFoundError, RemuxError) as exc:
        print(f"package: {exc}", file=sys.stderr)
        return 1
    for episode in episodes:
        print(episode)
    return 0


def _export(args: argparse.Namespace) -> int:
    """Export a packaged episode as a LeRobot v3.0 dataset directory. Needs ffmpeg, not the device."""
    try:
        lerobot = asyncio.run(export_lerobot_v3(Path(args.episode_dir)))
    except (ValueError, FileExistsError, FileNotFoundError, ExportError, RemuxError) as exc:
        print(f"export: {exc}", file=sys.stderr)
        return 1
    print(lerobot)
    return 0


def main(argv: list[str] | None = None, transport: Transport = None) -> int:
    parser = argparse.ArgumentParser(prog="pearl-episodes")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="check the environment and settings")
    sub.add_parser("recorders", help="list the device's recorders (id, name, multisource)")
    p_list = sub.add_parser("list", help="list recordings on one recorder")
    p_list.add_argument("recorder_id")
    p_pull = sub.add_parser(
        "pull", help="download new recordings from one recorder, skipping those already pulled"
    )
    p_pull.add_argument("recorder_id")
    p_exp = sub.add_parser(
        "export", help="export a packaged episode as a LeRobot v3.0 dataset (no re-encode)"
    )
    p_exp.add_argument("episode_dir")
    p_pkg = sub.add_parser(
        "package", help="package pulled files of one take as an episode (remux, no re-encode)"
    )
    p_pkg.add_argument(
        "--camera", nargs=4, action="append", required=True,
        metavar=("CHANNEL_ID", "CHANNEL_NAME", "RECORDER_ID", "FILE_IDS"),
        help="one camera: channel id and name, recorder id, comma-separated file ids; repeat per camera",
    )  # fmt: skip
    p_pkg.add_argument(
        "--serial", required=True, help="device serial number (from Edge; not in the REST API)"
    )
    p_pkg.add_argument("--model", required=True, help="device model, as `get_device_info` reports it")
    p_pkg.add_argument("--firmware", required=True)
    p_pkg.add_argument("--task", default="", help="task label")
    p_pkg.add_argument("--operator", default="")
    p_pkg.add_argument("--scene", default="")
    p_pkg.add_argument("--clock-source", choices=["ntp", "ptp", "manual", "unknown"], default="unknown")
    p_pkg.add_argument("--session", default=None, help="session id of the operator log")
    p_pkg.add_argument("--notes", default="")
    p_pkg.add_argument("--episode-id", default=None, help="default: <serial>-<first created>")
    args = parser.parse_args(argv)
    if args.cmd == "doctor":
        return _doctor()
    if args.cmd == "recorders":
        return _run(_recorders, transport)
    if args.cmd == "list":
        return _run(lambda client, settings: _list(client, settings, args.recorder_id), transport)
    if args.cmd == "pull":
        return _run(lambda client, settings: _pull(client, settings, args.recorder_id), transport)
    if args.cmd == "export":
        return _export(args)
    return _package(args)


if __name__ == "__main__":
    raise SystemExit(main())

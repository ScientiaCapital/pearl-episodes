"""pearl-episodes: doctor | recorders | list | pull | package

Every expected failure (settings missing, device unreachable, HTTP error, bad envelope) prints one line to
stderr and exits 1. Anything else is a bug and raises.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable

import httpx
from pydantic import ValidationError

from pearl_episodes import __version__
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
        from pearl_episodes.config import Settings

        s = Settings()
        print(f"  pearl host            {s.host} ({s.base_url})")
    except ValidationError as exc:
        print(f"  pearl settings        not configured ({_missing_settings(exc)}); copy .env.example to .env")
        ok = False
    return 0 if ok else 1


async def _recorders(client: PearlClient) -> None:
    for r in await client.list_recorders():
        print(f"{r.id}\t{r.name}\t{r.multisource}")


async def _list(client: PearlClient, recorder_id: str) -> None:
    for item in await client.list_recordings(recorder_id):
        print(f"{item.id}\t{item.created}\t{item.duration}\t{item.size}\t{item.name}")


def _run(action: Callable[[PearlClient], Awaitable[None]], transport: Transport) -> int:
    """Open a client from Settings, run `action`, map the expected failures to one stderr line and exit 1."""
    from pearl_episodes.config import Settings

    async def go() -> None:
        async with PearlClient(Settings(), transport=transport) as client:
            await action(client)

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


def main(argv: list[str] | None = None, transport: Transport = None) -> int:
    parser = argparse.ArgumentParser(prog="pearl-episodes")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="check the environment and settings")
    sub.add_parser("recorders", help="list the device's recorders (id, name, multisource)")
    p_list = sub.add_parser("list", help="list recordings on one recorder")
    p_list.add_argument("recorder_id")
    sub.add_parser("pull", help="download new recordings (not implemented)")
    sub.add_parser("package", help="package pulled recordings as episodes (not implemented)")
    args = parser.parse_args(argv)
    if args.cmd == "doctor":
        return _doctor()
    if args.cmd == "recorders":
        return _run(_recorders, transport)
    if args.cmd == "list":
        return _run(lambda client: _list(client, args.recorder_id), transport)
    print(f"{args.cmd}: not implemented yet; see .claude/TASK.md", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

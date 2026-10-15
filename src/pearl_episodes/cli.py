"""pearl-episodes: doctor | list | pull | package"""

from __future__ import annotations

import argparse
import asyncio
import sys

from pearl_episodes import __version__


def _doctor() -> int:
    import importlib.util

    print(f"pearl-episodes {__version__}")
    for mod in ("httpx", "pydantic", "pydantic_settings", "lerobot", "tensorflow", "tensorflow_datasets"):
        status = "ok" if importlib.util.find_spec(mod) else "missing"
        print(f"  {mod:22} {status}")
    try:
        from pearl_episodes.config import Settings

        s = Settings()
        print(f"  pearl host            {s.host} ({s.base_url})")
    except Exception as exc:  # noqa: BLE001
        print(f"  pearl settings        not configured ({exc.__class__.__name__}); copy .env.example to .env")
    return 0


async def _list(recorder_id: str) -> int:
    from pearl_episodes.config import Settings
    from pearl_episodes.pearl.client import PearlClient

    async with PearlClient(Settings()) as client:
        for item in await client.list_recordings(recorder_id):
            print(f"{item.id}\t{item.created}\t{item.duration}\t{item.size}\t{item.name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pearl-episodes")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="check the environment and settings")
    p_list = sub.add_parser("list", help="list recordings on one recorder")
    p_list.add_argument("recorder_id")
    sub.add_parser("pull", help="download new recordings (not implemented)")
    sub.add_parser("package", help="package pulled recordings as episodes (not implemented)")
    args = parser.parse_args(argv)
    if args.cmd == "doctor":
        return _doctor()
    if args.cmd == "list":
        return asyncio.run(_list(args.recorder_id))
    print(f"{args.cmd}: not implemented yet; see .claude/TASK.md", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

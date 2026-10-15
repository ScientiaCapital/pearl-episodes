"""Fail if a notebook has outputs, execution counts or attachments.

Notebooks are committed with outputs cleared: an output can embed a frame, and frames can show people.
Used by pre-commit (`.pre-commit-config.yaml`), and runnable by hand:

    python3 scripts/check_notebook_outputs.py notebooks/*.ipynb
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def check(path: Path) -> list[str]:
    """Problems found in one notebook; an empty list means it is clean."""
    try:
        notebook = json.loads(path.read_text())
        cells = notebook["cells"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"{path}: not a readable notebook ({exc.__class__.__name__})"]
    problems = []
    for number, cell in enumerate(cells):
        if cell.get("outputs"):
            problems.append(f"{path}: cell {number} has {len(cell['outputs'])} output(s); clear outputs")
        if cell.get("execution_count") is not None:
            problems.append(f"{path}: cell {number} has an execution count; clear outputs")
        if cell.get("attachments"):
            problems.append(f"{path}: cell {number} has attachments (embedded images); remove them")
    return problems


def main(argv: list[str] | None = None) -> int:
    problems = [p for name in (sys.argv[1:] if argv is None else argv) for p in check(Path(name))]
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

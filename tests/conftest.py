import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run every test from an empty folder with no PEARL_* variables, so a developer's .env never leaks in."""
    monkeypatch.chdir(tmp_path)
    for name in [n for n in os.environ if n.startswith("PEARL_")]:
        monkeypatch.delenv(name)

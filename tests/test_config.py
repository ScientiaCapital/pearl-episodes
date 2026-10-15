import os
from pathlib import Path

import pytest

from pearl_episodes.config import Settings


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run from an empty folder with no PEARL_* variables, so a developer's .env never leaks into a test."""
    monkeypatch.chdir(tmp_path)
    for name in [n for n in os.environ if n.startswith("PEARL_")]:
        monkeypatch.delenv(name)


def test_password_never_appears_in_repr_or_str() -> None:
    settings = Settings(host="pearl.test", password="not-a-real-password")
    assert "not-a-real-password" not in repr(settings)
    assert "not-a-real-password" not in str(settings)
    assert settings.password.get_secret_value() == "not-a-real-password"


def test_tls_is_verified_unless_turned_off(monkeypatch: pytest.MonkeyPatch) -> None:
    assert Settings(host="pearl.test").verify_tls is True
    monkeypatch.setenv("PEARL_VERIFY_TLS", "false")
    assert Settings(host="pearl.test").verify_tls is False

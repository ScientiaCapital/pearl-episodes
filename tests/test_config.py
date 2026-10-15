import pytest

from pearl_episodes.config import Settings


def test_password_never_appears_in_repr_or_str() -> None:
    settings = Settings(host="pearl.test", password="not-a-real-password")
    assert "not-a-real-password" not in repr(settings)
    assert "not-a-real-password" not in str(settings)
    assert settings.password.get_secret_value() == "not-a-real-password"


def test_tls_is_verified_unless_turned_off(monkeypatch: pytest.MonkeyPatch) -> None:
    assert Settings(host="pearl.test").verify_tls is True
    monkeypatch.setenv("PEARL_VERIFY_TLS", "false")
    assert Settings(host="pearl.test").verify_tls is False

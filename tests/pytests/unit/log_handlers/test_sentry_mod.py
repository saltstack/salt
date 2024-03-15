"""
Tests for salt.log_handlers.sentry_mod
"""

import pytest

import salt.log_handlers.sentry_mod
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    """
    Sentry log handler loader modules.
    """
    return {salt.log_handlers.sentry_mod: {"__grains__": {}, "__salt__": {}}}


@pytest.fixture
def sentry_handler():
    """
    Sentry log handler config data.
    """
    return {
        "sentry_handler": {
            "dsn": {"https://pub-key:secret-key@app.getsentry.com/app-id"}
        }
    }


def test___virtual___success(sentry_handler):
    """
    Test `__virtual__()` returns `__virtualname__`.
    """
    with patch("salt.log_handlers.sentry_mod.HAS_RAVEN", True), patch(
        "salt.log_handlers.sentry_mod.__opts__", sentry_handler
    ):
        ret = salt.log_handlers.sentry_mod.__virtual__()
    assert ret is salt.log_handlers.sentry_mod.__virtualname__


def test___virtual___fail(sentry_handler):
    """
    Test `__virtual__()` returns a reason for not loading.
    """
    with patch("salt.log_handlers.sentry_mod.HAS_RAVEN", False), patch(
        "salt.log_handlers.sentry_mod.__opts__", sentry_handler
    ):
        ret = salt.log_handlers.sentry_mod.__virtual__()
    assert ret[0] is False
    assert ret[1] == "Cannot find 'raven' python library"

    with patch("salt.log_handlers.sentry_mod.HAS_RAVEN", True), patch(
        "salt.log_handlers.sentry_mod.__opts__", {}
    ):
        ret = salt.log_handlers.sentry_mod.__virtual__()
    assert ret[0] is False
    assert ret[1] == "'sentry_handler' config is empty or not defined"


def test_setup_handlers_disabled_bypass_dunders():
    """
    Test that `setup_handlers()` returns before computing `__grains__` and
    `__salt__` dunders if `sentry_handler` is not configured.
    """
    with patch("salt.loader.grains", MagicMock()) as grains_loader, patch(
        "salt.loader.minion_mods", MagicMock()
    ) as salt_loader:
        ret = salt.log_handlers.sentry_mod.setup_handlers()
    assert ret is False
    grains_loader.assert_not_called()
    salt_loader.assert_not_called()
